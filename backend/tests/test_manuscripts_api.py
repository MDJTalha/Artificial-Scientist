"""API tests for the tenant-safe, evidence-linked manuscript drafting flow."""

from uuid import uuid4

from fastapi.testclient import TestClient

from artificial_scientist.api.routes import records as records_routes
from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.main import app
from artificial_scientist.records.models import SourceRecord
from artificial_scientist.records.store import RecordStore


def _source(store: RecordStore, *, tenant_id: str | None = None, status: str = "unassessed"):
    return store.create(
        SourceRecord(
            title="A scholarly metadata record",
            source_url="https://example.org/article",
            external_identifier=f"doi:10.1234/{uuid4()}",
            assessment_status=status,
        ),
        tenant_id=tenant_id,
    )


def _request_payload(source_id):
    return {
        "title": "A bounded scientific draft",
        "abstract": "A researcher-authored abstract for a structured draft.",
        "claims": [
            {
                "text": "This is a carefully qualified researcher-supplied claim.",
                "source_record_ids": [str(source_id)],
            }
        ],
        "methods": "The researcher describes the methods and analysis approach here.",
        "limitations": "The available evidence and methodological limitations are stated here.",
        "data_statement": "Data availability and access restrictions are described here.",
    }


def test_manuscript_draft_is_persisted_with_verified_record_citations(
    monkeypatch, tmp_path
):
    store = RecordStore(tmp_path / "manuscripts.sqlite3")
    source = _source(store)
    app.dependency_overrides[get_record_store] = lambda: store

    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/manuscripts",
                json=_request_payload(source.id),
            )
            assert created.status_code == 201
            envelope = created.json()
            assert envelope["record_type"] == "manuscript"
            assert envelope["payload"]["status"] == "draft"
            assert envelope["payload"]["submission_approved"] is False
            assert envelope["payload"]["claims"][0]["source_record_ids"] == [
                str(source.id)
            ]
            markdown = envelope["payload"]["rendered_markdown"]
            assert "Draft status" in markdown
            assert "## References" in markdown
            assert "does not establish that the source supports" in markdown
            assert "External submission and publication are disabled" in markdown

            listing = client.get("/api/v1/manuscripts")
            assert listing.status_code == 200
            assert listing.json()["total"] == 1
            assert listing.json()["items"][0]["id"] == envelope["id"]
            assert listing.json()["items"][0]["citation_count"] == 1

            fetched = client.get(f"/api/v1/manuscripts/{envelope['id']}")
            assert fetched.status_code == 200
            assert fetched.json()["payload"]["rendered_markdown"] == markdown
    finally:
        app.dependency_overrides.pop(get_record_store, None)


def test_manuscript_rejects_cross_tenant_citations(
    monkeypatch, tmp_path
):
    database = tmp_path / "manuscript-tenants.sqlite3"
    store = RecordStore(database)
    source_a = _source(store, tenant_id="tenant-a")
    app.dependency_overrides[get_record_store] = lambda: store
    monkeypatch.setattr(
        records_routes,
        "require_record_access",
        lambda request, action, authorization, x_tenant_id: x_tenant_id,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/manuscripts",
                headers={"X-Tenant-ID": "tenant-b"},
                json=_request_payload(source_a.id),
            )
            assert response.status_code == 422
            assert "not available in this tenant" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_record_store, None)


def test_manuscript_rejects_missing_identifiers_and_retracted_sources(tmp_path):
    store = RecordStore(tmp_path / "manuscript-invalid-sources.sqlite3")
    missing_identifier = store.create(
        SourceRecord(
            title="A source without an external identifier",
            source_url="https://example.org/no-id",
        )
    )
    retracted = _source(store, status="retracted")
    app.dependency_overrides[get_record_store] = lambda: store

    try:
        with TestClient(app) as client:
            no_identifier = client.post(
                "/api/v1/manuscripts",
                json=_request_payload(missing_identifier.id),
            )
            assert no_identifier.status_code == 422
            assert "no external identifier" in no_identifier.json()["detail"]

            retracted_response = client.post(
                "/api/v1/manuscripts",
                json=_request_payload(retracted.id),
            )
            assert retracted_response.status_code == 422
            assert "marked retracted" in retracted_response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_record_store, None)
