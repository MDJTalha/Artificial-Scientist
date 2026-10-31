"""Deterministic tests for scholarly metadata retrieval and evidence provenance."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from artificial_scientist.config import get_settings
from artificial_scientist.literature.models import LiteratureSearchRequest
from artificial_scientist.literature.providers import (
    CrossrefProvider,
    LiteratureProviderError,
    OpenAlexProvider,
)
from artificial_scientist.literature.service import LiteratureService
from artificial_scientist.main import app
from artificial_scientist.records.identity import normalize_doi
from artificial_scientist.records.models import SourceRecord
from artificial_scientist.records.store import RecordStore

DOI = "10.1234/science.example.2025.01"
QUERY = "numerical methods for differential equations"


def openalex_work(
    *,
    doi: str | None = DOI,
    title: str = "A study of numerical methods",
) -> dict[str, Any]:
    return {
        "id": "https://openalex.org/W1234567890",
        "doi": f"https://doi.org/{doi}" if doi else None,
        "title": title,
        "publication_date": "2025-04-02",
        "publication_year": 2025,
        "authorships": [
            {"author": {"display_name": "Ada Researcher"}},
            {"author": {"display_name": "Lin Scientist"}},
        ],
        "type": "article",
        "primary_location": {
            "landing_page_url": "https://publisher.example/research/article"
        },
        "best_oa_location": {
            "landing_page_url": "https://repository.example/article"
        },
        "is_retracted": False,
        "cited_by_count": 3,
    }


def crossref_work(
    *,
    doi: str = DOI,
    title: str = "A study of numerical methods",
) -> dict[str, Any]:
    return {
        "DOI": doi,
        "title": [title],
        "author": [
            {"given": "Ada", "family": "Researcher"},
            {"given": "Lin", "family": "Scientist"},
        ],
        "published-online": {"date-parts": [[2025, 4, 2]]},
        "type": "journal-article",
        "URL": f"https://doi.org/{doi}",
        "container-title": ["Journal of Example Research"],
        "is-referenced-by-count": 7,
    }


def handler_for(
    *,
    openalex_status: int = 200,
    crossref_status: int = 200,
    openalex_payload: object | None = None,
    crossref_payload: object | None = None,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.openalex.org":
            if openalex_status != 200:
                return httpx.Response(
                    openalex_status,
                    json={"error": "upstream detail not exposed"},
                )
            payload = openalex_payload
            if payload is None:
                payload = {"results": [openalex_work()]}
            return httpx.Response(200, json=payload, headers={"content-type": "application/json"})
        if request.url.host == "api.crossref.org":
            if crossref_status != 200:
                return httpx.Response(crossref_status, json={"message": "upstream failure"})
            payload = crossref_payload
            if payload is None:
                payload = {"message": {"items": [crossref_work()]}}
            return httpx.Response(200, json=payload, headers={"content-type": "application/json"})
        raise AssertionError(f"unexpected outbound host: {request.url.host}")

    return httpx.MockTransport(handler)


@pytest.fixture
def store(tmp_path: Path) -> RecordStore:
    return RecordStore(tmp_path / "literature.sqlite3")


def make_service(
    store: RecordStore,
    transport: httpx.BaseTransport,
) -> LiteratureService:
    return LiteratureService(
        store=store,
        settings=get_settings(),
        transport=transport,
    )


def test_doi_normalization_accepts_common_representations() -> None:
    assert normalize_doi(DOI) == DOI
    assert normalize_doi(f"https://doi.org/{DOI.upper()}") == DOI
    assert normalize_doi(f"doi: {DOI}") == DOI
    assert normalize_doi("not-a-doi") is None
    assert normalize_doi(None) is None


def test_openalex_provider_normalizes_metadata_and_sends_bounded_query() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={"results": [openalex_work()]},
            headers={"content-type": "application/json"},
        )

    settings = replace(get_settings(), openalex_api_key="test-key")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        works = OpenAlexProvider().search(client, QUERY, 4, settings)

    assert len(seen) == 1
    assert seen[0].url.host == "api.openalex.org"
    assert seen[0].url.params.get("per_page") == "4"
    assert seen[0].headers.get("authorization") == "Bearer test-key"
    assert len(works) == 1
    assert works[0].doi == DOI
    assert works[0].authors == ["Ada Researcher", "Lin Scientist"]
    assert works[0].source_kind == "journal_article"
    assert str(works[0].source_url) == f"https://doi.org/{DOI}"


def test_crossref_provider_normalizes_date_authors_and_doi() -> None:
    with httpx.Client(
        transport=handler_for(
            openalex_status=503,
            crossref_payload={"message": {"items": [crossref_work()]}},
        )
    ) as client:
        work = CrossrefProvider().search(client, QUERY, 5, get_settings())[0]

    assert work.provider == "crossref"
    assert work.doi == DOI
    assert work.publication_date.isoformat() == "2025-04-02"
    assert work.publication_year == 2025
    assert work.authors == ["Ada Researcher", "Lin Scientist"]
    assert work.source_kind == "journal_article"


def test_search_deduplicates_doi_and_persists_source_provenance(store: RecordStore) -> None:
    service = make_service(store, handler_for())
    result = service.search(LiteratureSearchRequest(query=QUERY, limit=5))

    assert result.status == "ok"
    assert result.total_results == 1
    work = result.results[0]
    assert work.doi == DOI
    assert work.matched_providers == ["openalex", "crossref"]
    assert work.provider_identifiers["openalex"] == "W1234567890"
    assert work.cited_by_count == 7
    assert work.saved_record_id is not None

    saved = store.get(work.saved_record_id)
    payload = saved.payload
    assert payload["record_type"] == "source"
    assert payload["external_identifier"] == f"doi:{DOI}"
    assert payload["assessment_status"] == "unassessed"
    assert payload["provenance"]["method"] == "literature_retrieval"
    assert "providers=openalex,crossref" in payload["provenance"]["notes"]
    assert f"query={QUERY}" in payload["provenance"]["notes"]
    source_records, total = store.list_records(record_type="source")
    assert total == 1
    assert len(source_records) == 1


def test_repeated_search_reuses_existing_source_record(store: RecordStore) -> None:
    first = make_service(store, handler_for()).search(
        LiteratureSearchRequest(query=QUERY, providers=["openalex"])
    )
    second = make_service(store, handler_for()).search(
        LiteratureSearchRequest(
            query="another wording for a related search", providers=["crossref"]
        )
    )

    assert first.results[0].saved_record_id == second.results[0].saved_record_id
    _, total = store.list_records(record_type="source")
    assert total == 1


def test_search_can_return_metadata_without_persisting(store: RecordStore) -> None:
    result = make_service(store, handler_for()).search(
        LiteratureSearchRequest(query=QUERY, persist_results=False)
    )

    assert result.total_results == 1
    assert result.results[0].saved_record_id is None
    _, total = store.list_records(record_type="source")
    assert total == 0


@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [(429, "rate_limited"), (503, "unavailable"), (302, "invalid_response")],
)
def test_provider_failures_are_classified_without_leaking_body(
    store: RecordStore, status_code: int, expected_status: str
) -> None:
    result = make_service(
        store,
        handler_for(openalex_status=status_code, crossref_payload={"message": {"items": []}}),
    ).search(LiteratureSearchRequest(query=QUERY, providers=["openalex", "crossref"]))

    assert result.status == "partial"
    failed = result.providers[0]
    assert failed.provider == "openalex"
    assert failed.status == expected_status
    assert "upstream detail" not in (failed.message or "")
    assert len(result.providers) == 2


def test_all_providers_failed_is_explicit_and_does_not_create_records(store: RecordStore) -> None:
    result = make_service(
        store,
        handler_for(openalex_status=503, crossref_status=429),
    ).search(LiteratureSearchRequest(query=QUERY))

    assert result.status == "unavailable"
    assert result.total_results == 0
    assert {item.status for item in result.providers} == {"unavailable", "rate_limited"}
    _, total = store.list_records(record_type="source")
    assert total == 0


def test_malformed_provider_payload_is_not_presented_as_a_success(store: RecordStore) -> None:
    result = make_service(
        store,
        handler_for(
            openalex_payload={"unexpected": "shape"},
            crossref_payload={"message": {"items": []}},
        ),
    ).search(LiteratureSearchRequest(query=QUERY))

    assert result.status == "partial"
    assert result.providers[0].status == "invalid_response"
    assert result.results == []


def test_non_json_redirect_and_oversize_responses_are_rejected() -> None:
    def redirect_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.net/collect"})

    with httpx.Client(transport=httpx.MockTransport(redirect_handler)) as client:
        with pytest.raises(LiteratureProviderError) as error:
            OpenAlexProvider().search(client, QUERY, 3, get_settings())
    assert error.value.code == "invalid_response"

    def oversize_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x" * (2 * 1024 * 1024 + 1),
            headers={"content-type": "application/json"},
        )

    with httpx.Client(transport=httpx.MockTransport(oversize_handler)) as client:
        with pytest.raises(LiteratureProviderError) as oversized:
            OpenAlexProvider().search(client, QUERY, 3, get_settings())
    assert oversized.value.code == "invalid_response"


def test_invalid_provider_record_fields_are_skipped_safely() -> None:
    payload = {
        "results": [
            {"id": "https://openalex.org/W1", "title": "", "type": "article"},
            openalex_work(),
        ]
    }
    with httpx.Client(
        transport=handler_for(openalex_payload=payload, crossref_status=503)
    ) as client:
        work = OpenAlexProvider().search(client, QUERY, 5, get_settings())
    assert len(work) == 1
    assert work[0].title == "A study of numerical methods"


def test_literature_api_validation_and_response_contract(
    store: RecordStore,
) -> None:
    service = make_service(store, handler_for())
    from artificial_scientist.api.routes.literature import get_literature_service

    app.dependency_overrides[get_literature_service] = lambda: service
    try:
        with TestClient(app) as client:
            invalid = client.post(
                "/api/v1/literature/search",
                json={"query": "x", "limit": 999, "extra": True},
            )
            assert invalid.status_code == 422

            valid = client.post(
                "/api/v1/literature/search",
                json={
                    "query": QUERY,
                    "limit": 5,
                    "providers": ["openalex", "crossref"],
                    "persist_results": False,
                },
            )
            assert valid.status_code == 200
            body = valid.json()
            assert body["status"] == "ok"
            assert body["total_results"] == 1
            assert body["results"][0]["doi"] == DOI
            assert len(body["providers"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_source_identity_index_migrates_existing_schema_v1_records(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "old-schema.sqlite3"
    source = SourceRecord(
        title="Existing source record",
        source_url=f"https://doi.org/{DOI}",
        external_identifier=f"doi:{DOI}",
    )
    payload_json = json.dumps(
        source.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE research_records (
                id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE audit_events (
                event_id TEXT PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                record_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                content_sha256 TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO research_records
                (id, record_type, schema_version, created_at, content_sha256, payload_json)
            VALUES (?, 'source', 1, ?, ?, ?)
            """,
            (str(source.id), datetime.now(UTC).isoformat(), digest, payload_json),
        )
        connection.execute("PRAGMA user_version = 1")

    migrated = RecordStore(database_path)
    assert migrated.get(source.id).content_sha256 == digest
    existing = migrated.find_source_by_identity(source)
    assert existing is not None
    assert existing.id == source.id

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
