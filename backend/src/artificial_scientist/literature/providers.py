"""Bounded, source-aware connectors for OpenAlex and Crossref metadata APIs.

Only fixed provider endpoints are requested. Returned landing-page URLs are stored
as metadata and are never fetched by this module.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, ValidationError

from artificial_scientist.config import Settings
from artificial_scientist.records.identity import normalize_doi

ProviderName = Literal["openalex", "crossref"]
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)
USER_AGENT = (
    "ArtificialScientist/0.1.0 "
    "(research project; https://github.com/MDJTalha/Artificial-Scientist)"
)


class LiteratureProviderError(Exception):
    """An upstream provider failed without exposing its response body."""

    def __init__(self, provider: ProviderName, code: str, message: str) -> None:
        self.provider = provider
        self.code = code
        self.public_message = message
        super().__init__(f"{provider}: {code}")


class ProviderWork(BaseModel):
    """Normalized metadata from one provider, before cross-provider deduplication."""

    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    provider_identifier: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=2, max_length=500)
    authors: list[str] = Field(default_factory=list, max_length=100)
    doi: str | None = Field(default=None, max_length=300)
    publication_date: date | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=9999)
    source_url: HttpUrl
    source_kind: Literal[
        "journal_article", "preprint", "dataset", "standard", "other"
    ] = "other"
    is_retracted: bool | None = None
    has_open_access_location: bool | None = None
    cited_by_count: int | None = Field(default=None, ge=0)


def _read_json(
    client: httpx.Client,
    *,
    provider: ProviderName,
    url: str,
    params: dict[str, str | int],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Read bounded JSON from a fixed, trusted API endpoint."""
    try:
        with client.stream(
            "GET",
            url,
            params=params,
            headers=headers or {},
            follow_redirects=False,
        ) as response:
            if 300 <= response.status_code < 400:
                raise LiteratureProviderError(
                    provider, "invalid_response", "Provider returned an unexpected redirect."
                )
            if response.status_code == 429:
                raise LiteratureProviderError(
                    provider, "rate_limited", "Provider rate limit reached; retry later."
                )
            if response.status_code >= 500:
                raise LiteratureProviderError(
                    provider, "unavailable", "Provider is temporarily unavailable."
                )
            if response.status_code >= 400:
                raise LiteratureProviderError(
                    provider, "unavailable", "Provider rejected the metadata request."
                )

            content_type = response.headers.get("content-type", "").lower()
            if "json" not in content_type:
                raise LiteratureProviderError(
                    provider, "invalid_response", "Provider did not return JSON metadata."
                )
            declared_length = response.headers.get("content-length")
            if declared_length and declared_length.isdigit():
                if int(declared_length) > MAX_RESPONSE_BYTES:
                    raise LiteratureProviderError(
                        provider, "invalid_response", "Provider response exceeded the size limit."
                    )

            body = bytearray()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise LiteratureProviderError(
                        provider, "invalid_response", "Provider response exceeded the size limit."
                    )
                body.extend(chunk)

    except LiteratureProviderError:
        raise
    except httpx.TimeoutException as exc:
        raise LiteratureProviderError(
            provider, "unavailable", "Provider request timed out."
        ) from exc
    except httpx.RequestError as exc:
        raise LiteratureProviderError(
            provider, "unavailable", "Provider network request failed."
        ) from exc

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LiteratureProviderError(
            provider, "invalid_response", "Provider returned malformed JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise LiteratureProviderError(
            provider, "invalid_response", "Provider returned an unexpected JSON structure."
        )
    return payload


def _safe_web_url(value: object) -> str | None:
    """Accept only normal HTTP(S) metadata URLs; never dereference the URL."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not (candidate[:8].casefold() == "https://" or candidate[:7].casefold() == "http://"):
        return None
    try:
        return str(HTTP_URL_ADAPTER.validate_python(candidate))
    except ValidationError:
        return None


def _date_from_parts(value: object) -> date | None:
    """Keep exact dates only; do not invent month/day when metadata is incomplete."""
    if not isinstance(value, dict):
        return None
    date_parts = value.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts:
        return None
    first = date_parts[0]
    if not isinstance(first, list) or len(first) < 3:
        return None
    try:
        return date(int(first[0]), int(first[1]), int(first[2]))
    except (TypeError, ValueError, OverflowError):
        return None


def _date_from_iso(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _author_names(value: object, *, openalex: bool) -> list[str]:
    if not isinstance(value, list):
        return []
    authors: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if openalex:
            author = item.get("author")
            name = author.get("display_name") if isinstance(author, dict) else None
        else:
            given = item.get("given")
            family = item.get("family")
            name = " ".join(
                part.strip() for part in (given, family)
                if isinstance(part, str) and part.strip()
            )
            if not name:
                name = item.get("name")
        if isinstance(name, str) and name.strip():
            cleaned = " ".join(name.split())
            if cleaned not in authors and len(authors) < 100:
                authors.append(cleaned[:300])
    return authors


def _source_kind(raw_type: object) -> Literal[
    "journal_article", "preprint", "dataset", "standard", "other"
]:
    normalized = str(raw_type or "").casefold().replace("_", "-")
    if "preprint" in normalized or normalized == "posted-content":
        return "preprint"
    if "dataset" in normalized:
        return "dataset"
    if "standard" in normalized:
        return "standard"
    if normalized in {"article", "journal-article", "review", "proceedings-article"}:
        return "journal_article"
    return "other"


def _first_nonempty(values: list[object]) -> object | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class OpenAlexProvider:
    """OpenAlex Works metadata search."""

    name: ProviderName = "openalex"
    endpoint = "https://api.openalex.org/works"

    def search(
        self, client: httpx.Client, query: str, limit: int, settings: Settings
    ) -> list[ProviderWork]:
        params: dict[str, str | int] = {
            "search": query,
            "per_page": limit,
            "select": (
                "id,doi,title,publication_date,publication_year,authorships,type,"
                "primary_location,best_oa_location,is_retracted,cited_by_count"
            ),
        }
        if settings.crossref_contact_email:
            params["mailto"] = settings.crossref_contact_email
        headers = (
            {"Authorization": f"Bearer {settings.openalex_api_key}"}
            if settings.openalex_api_key
            else {}
        )
        payload = _read_json(
            client, provider=self.name, url=self.endpoint, params=params, headers=headers
        )
        rows = payload.get("results")
        if not isinstance(rows, list):
            raise LiteratureProviderError(
                self.name, "invalid_response", "OpenAlex response omitted the results array."
            )

        works: list[ProviderWork] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            title = row.get("title")
            identifier = row.get("id")
            if not isinstance(title, str) or len(title.strip()) < 2:
                continue
            if not isinstance(identifier, str) or not identifier.startswith("https://openalex.org/"):
                continue
            doi = normalize_doi(row.get("doi") if isinstance(row.get("doi"), str) else None)
            location_values: list[object] = []
            for key in ("best_oa_location", "primary_location"):
                location = row.get(key)
                if isinstance(location, dict):
                    location_values.append(location.get("landing_page_url"))
            landing = _safe_web_url(doi and f"https://doi.org/{doi}")
            if landing is None:
                landing = _safe_web_url(_first_nonempty(location_values))
            if landing is None:
                landing = _safe_web_url(identifier)
            if landing is None:
                continue
            pub_date = _date_from_iso(row.get("publication_date"))
            year_raw = row.get("publication_year")
            year = year_raw if isinstance(year_raw, int) and 1000 <= year_raw <= 9999 else (
                pub_date.year if pub_date else None
            )
            oa_location = row.get("best_oa_location")
            oa = isinstance(oa_location, dict) and bool(oa_location.get("landing_page_url"))
            cited = row.get("cited_by_count")
            if not isinstance(cited, int) or cited < 0:
                cited = None
            retracted = row.get("is_retracted")
            if not isinstance(retracted, bool):
                retracted = None
            try:
                works.append(
                    ProviderWork(
                        provider=self.name,
                        provider_identifier=identifier.removeprefix("https://openalex.org/"),
                        title=" ".join(title.split())[:500],
                        authors=_author_names(row.get("authorships"), openalex=True),
                        doi=doi,
                        publication_date=pub_date,
                        publication_year=year,
                        source_url=landing,
                        source_kind=_source_kind(row.get("type")),
                        is_retracted=retracted,
                        has_open_access_location=oa,
                        cited_by_count=cited,
                    )
                )
            except ValidationError:
                continue
        return works


class CrossrefProvider:
    """Crossref Works metadata search through its public REST API."""

    name: ProviderName = "crossref"
    endpoint = "https://api.crossref.org/works"

    def search(
        self, client: httpx.Client, query: str, limit: int, settings: Settings
    ) -> list[ProviderWork]:
        params: dict[str, str | int] = {
            "query.bibliographic": query,
            "rows": limit,
            "select": (
                "DOI,title,author,published,published-print,published-online,type,URL,"
                "container-title,is-referenced-by-count"
            ),
        }
        if settings.crossref_contact_email:
            params["mailto"] = settings.crossref_contact_email
        payload = _read_json(
            client,
            provider=self.name,
            url=self.endpoint,
            params=params,
        )
        message = payload.get("message")
        rows = message.get("items") if isinstance(message, dict) else None
        if not isinstance(rows, list):
            raise LiteratureProviderError(
                self.name, "invalid_response", "Crossref response omitted the works array."
            )

        works: list[ProviderWork] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            title_value = row.get("title")
            title = title_value[0] if isinstance(title_value, list) and title_value else None
            if not isinstance(title, str) or len(title.strip()) < 2:
                continue
            raw_doi = row.get("DOI")
            doi = normalize_doi(raw_doi if isinstance(raw_doi, str) else None)
            raw_url = f"https://doi.org/{doi}" if doi else _safe_web_url(row.get("URL"))
            landing = _safe_web_url(raw_url)
            if landing is None:
                continue
            pub_date = (
                _date_from_parts(row.get("published-online"))
                or _date_from_parts(row.get("published-print"))
                or _date_from_parts(row.get("published"))
            )
            year = pub_date.year if pub_date else None
            if year is None:
                for field in ("published-online", "published-print", "published"):
                    date_value = row.get(field)
                    date_parts = date_value.get("date-parts") if isinstance(date_value, dict) else None
                    first = date_parts[0] if isinstance(date_parts, list) and date_parts else None
                    candidate = first[0] if isinstance(first, list) and first else None
                    if isinstance(candidate, int) and 1000 <= candidate <= 9999:
                        year = candidate
                        break
            cited = row.get("is-referenced-by-count")
            if not isinstance(cited, int) or cited < 0:
                cited = None
            doi_id = doi or str(row.get("URL") or title).strip()
            try:
                works.append(
                    ProviderWork(
                        provider=self.name,
                        provider_identifier=doi_id[:500],
                        title=" ".join(title.split())[:500],
                        authors=_author_names(row.get("author"), openalex=False),
                        doi=doi,
                        publication_date=pub_date,
                        publication_year=year,
                        source_url=landing,
                        source_kind=_source_kind(row.get("type")),
                        is_retracted=None,
                        has_open_access_location=None,
                        cited_by_count=cited,
                    )
                )
            except ValidationError:
                continue
        return works
