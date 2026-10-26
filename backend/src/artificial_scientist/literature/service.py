"""Scholarly literature search, normalization, deduplication, and provenance."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Literal

import httpx

from artificial_scientist.config import Settings, get_settings
from artificial_scientist.literature.models import (
    LiteratureResult,
    LiteratureSearchRequest,
    LiteratureSearchResponse,
    ProviderSearchStatus,
)
from artificial_scientist.literature.providers import (
    CrossrefProvider,
    LiteratureProviderError,
    OpenAlexProvider,
    ProviderName,
    ProviderWork,
)
from artificial_scientist.records.identity import source_identity_key
from artificial_scientist.records.models import Provenance, SourceRecord
from artificial_scientist.records.store import (
    DuplicateSource,
    RecordStore,
    RecordStoreError,
)

SearchStatus = Literal["ok", "partial", "unavailable"]


class LiteraturePersistenceError(Exception):
    """The search completed, but metadata could not be safely persisted."""


class LiteratureService:
    """Retrieve citation metadata from permitted APIs; never download source documents."""

    def __init__(
        self,
        store: RecordStore,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.store = store
        self.settings = settings or get_settings()
        self.transport = transport

    @staticmethod
    def _client(transport: httpx.BaseTransport | None) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(8.0, connect=3.0, read=8.0, write=3.0, pool=3.0),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            follow_redirects=False,
            headers={
                "User-Agent": (
                    "ArtificialScientist/0.1.0 "
                    "(research project; https://github.com/MDJTalha/Artificial-Scientist)"
                ),
                "Accept": "application/json",
            },
            transport=transport,
        )

    @staticmethod
    def _source_record(
        item: LiteratureResult,
        *,
        query: str,
        retrieved_at: datetime,
    ) -> SourceRecord:
        provider_ids = json.dumps(item.provider_identifiers, sort_keys=True)
        external_identifier = (
            f"doi:{item.doi}"
            if item.doi
            else (
                f"{item.matched_providers[0]}:"
                f"{item.provider_identifiers[item.matched_providers[0]]}"
            )
        )
        providers_text = ",".join(item.matched_providers)
        notes = (
            f"query={query}; providers={providers_text}; provider_identifiers={provider_ids}; "
            "metadata_only=true; source document was not downloaded or evaluated"
        )
        return SourceRecord(
            title=item.title,
            source_url=item.source_url,
            source_kind=item.source_kind,
            authors=item.authors,
            published_date=item.publication_date,
            retrieved_at=retrieved_at,
            external_identifier=external_identifier[:300],
            assessment_status="unassessed",
            provenance=Provenance(
                method="literature_retrieval",
                tool_name="OpenAlex/Crossref metadata connectors",
                captured_at=retrieved_at,
                notes=notes[:4000],
            ),
        )

    @staticmethod
    def _work_to_result(work: ProviderWork) -> LiteratureResult:
        return LiteratureResult(
            title=work.title,
            authors=work.authors,
            doi=work.doi,
            publication_date=work.publication_date,
            publication_year=work.publication_year,
            source_url=work.source_url,
            source_kind=work.source_kind,
            provider_identifiers={work.provider: work.provider_identifier},
            matched_providers=[work.provider],
            is_retracted=work.is_retracted,
            has_open_access_location=work.has_open_access_location,
            cited_by_count=work.cited_by_count,
        )

    @staticmethod
    def _identity_for_result(item: LiteratureResult) -> str:
        external_identifier = (
            f"doi:{item.doi}"
            if item.doi
            else (
                f"{item.matched_providers[0]}:"
                f"{item.provider_identifiers[item.matched_providers[0]]}"
            )
        )
        return source_identity_key(
            SourceRecord(
                title=item.title,
                source_url=item.source_url,
                external_identifier=external_identifier[:300],
            )
        )

    @staticmethod
    def _merge_result(existing: LiteratureResult, incoming: LiteratureResult) -> None:
        """Combine provider coverage without asserting that either source is correct."""
        for provider in incoming.matched_providers:
            if provider not in existing.matched_providers:
                existing.matched_providers.append(provider)
            existing.provider_identifiers[provider] = incoming.provider_identifiers[provider]

        for author in incoming.authors:
            if author not in existing.authors and len(existing.authors) < 100:
                existing.authors.append(author)
        if existing.doi is None:
            existing.doi = incoming.doi
        if existing.publication_date is None:
            existing.publication_date = incoming.publication_date
        if existing.publication_year is None:
            existing.publication_year = incoming.publication_year
        if existing.source_kind == "other" and incoming.source_kind != "other":
            existing.source_kind = incoming.source_kind
        if incoming.is_retracted is True:
            existing.is_retracted = True
        elif existing.is_retracted is None:
            existing.is_retracted = incoming.is_retracted
        if incoming.has_open_access_location is True:
            existing.has_open_access_location = True
        elif existing.has_open_access_location is None:
            existing.has_open_access_location = incoming.has_open_access_location
        if incoming.cited_by_count is not None:
            existing.cited_by_count = max(
                existing.cited_by_count or 0, incoming.cited_by_count
            )
        # A DOI URL is a stable landing URL; prefer it over a provider landing page.
        if incoming.doi:
            existing.source_url = incoming.source_url

    def search(self, request: LiteratureSearchRequest) -> LiteratureSearchResponse:
        """Search the selected providers, deduplicate works, and optionally persist metadata."""
        provider_map = {
            "openalex": OpenAlexProvider(),
            "crossref": CrossrefProvider(),
        }
        statuses: list[ProviderSearchStatus] = []
        by_identity: dict[str, LiteratureResult] = {}
        retrieved_at = datetime.now(UTC)

        with self._client(self.transport) as client:
            for provider_name in request.providers:
                provider = provider_map[provider_name]
                try:
                    works = provider.search(
                        client, request.query, request.limit, self.settings
                    )
                except LiteratureProviderError as error:
                    statuses.append(
                        ProviderSearchStatus(
                            provider=provider_name,
                            status=error.code,  # validated Literal from connector
                            result_count=0,
                            message=error.public_message,
                        )
                    )
                    continue
                except Exception:
                    # Provider-specific parse bugs must not leak bodies, secrets, or
                    # exception details to clients, and should not erase other results.
                    statuses.append(
                        ProviderSearchStatus(
                            provider=provider_name,
                            status="invalid_response",
                            result_count=0,
                            message="Provider response could not be normalized safely.",
                        )
                    )
                    continue

                statuses.append(
                    ProviderSearchStatus(
                        provider=provider_name,
                        status="ok",
                        result_count=len(works),
                    )
                )
                for work in works:
                    candidate = self._work_to_result(work)
                    identity = self._identity_for_result(candidate)
                    existing = by_identity.get(identity)
                    if existing is None:
                        by_identity[identity] = candidate
                    else:
                        self._merge_result(existing, candidate)

        results = list(by_identity.values())[: request.limit]
        successful_count = sum(1 for status in statuses if status.status == "ok")
        overall_status: SearchStatus
        if successful_count == len(statuses):
            overall_status = "ok"
        elif successful_count:
            overall_status = "partial"
        else:
            overall_status = "unavailable"

        if request.persist_results and overall_status != "unavailable":
            for item in results:
                source_record = self._source_record(
                    item, query=request.query, retrieved_at=retrieved_at
                )
                try:
                    existing_record = self.store.find_source_by_identity(source_record)
                    if existing_record is None:
                        try:
                            saved = self.store.create(source_record)
                        except DuplicateSource as duplicate:
                            saved = self.store.get(duplicate.existing_record_id)
                        item.saved_record_id = saved.id
                    else:
                        item.saved_record_id = existing_record.id
                except RecordStoreError as exc:
                    raise LiteraturePersistenceError(
                        "Literature metadata was retrieved, but a source record could not be saved."
                    ) from exc

        return LiteratureSearchResponse(
            query=request.query,
            retrieved_at=retrieved_at,
            status=overall_status,
            results=results,
            total_results=len(results),
            providers=statuses,
        )
