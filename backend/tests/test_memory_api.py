"""API regressions for evidence-linked, tenant-scoped scientific memory."""

from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from artificial_scientist.api.routes import memory as memory_routes
from artificial_scientist.api.routes import records as records_routes
from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.main import app
from artificial_scientist.records.models import SourceRecord
from artificial_scientist.records.store import RecordStore


def test_memory_api_versions_contradictions_and_rollback(monkeypatch, tmp_path):
    database = str(tmp_path / "scientific-memory.sqlite3")
    store = RecordStore(database)
    source = store.create(
        SourceRecord(
            title="A verified metadata source",
            source_url="https://example.org/evidence",
            external_identifier=f"doi:10.1234/{uuid4()}",
        )
    )
    monkeypatch.setattr(
        memory_routes,
        "get_settings",
        lambda: SimpleNamespace(database_path=database),
    )
    app.dependency_overrides[get_record_store] = lambda: store

    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/memory/reaction-rate",
                json={
                    "value": {
                        "statement": "The measured rate increases under condition A."
                    },
                    "evidence_record_ids": [str(source.id)],
                },
            )
            assert created.status_code == 201
            first = created.json()
            assert first["version"] == 1
            assert first["status"] == "active"
            assert first["evidence"] == [str(source.id)]
            assert len(first["digest"]) == 64

            listing = client.get("/api/v1/memory")
            assert listing.status_code == 200
            assert listing.json()["total"] == 1
            assert listing.json()["items"][0]["key"] == "reaction-rate"

            contradiction = client.post(
                "/api/v1/memory/reaction-rate/contradict",
                json={
                    "reason": (
                        "A documented repeat measurement conflicts with the current memory."
                    ),
                    "evidence_record_ids": [str(source.id)],
                },
            )
            assert contradiction.status_code == 201
            disputed = contradiction.json()
            assert disputed["version"] == 2
            assert disputed["status"] == "disputed"
            assert disputed["supersedes"] == 1

            history = client.get("/api/v1/memory/reaction-rate")
            assert history.status_code == 200
            assert [item["version"] for item in history.json()["items"]] == [1, 2]

            rollback = client.post(
                "/api/v1/memory/reaction-rate/rollback",
                json={"version": 1},
            )
            assert rollback.status_code == 201
            restored = rollback.json()
            assert restored["version"] == 3
            assert restored["status"] == "rollback"
            assert restored["value"] == first["value"]
            assert restored["supersedes"] == 2

            missing = client.post(
                "/api/v1/memory/unverified",
                json={
                    "value": {"statement": "unverified"},
                    "evidence_record_ids": [str(uuid4())],
                },
            )
            assert missing.status_code == 422
            assert "not available in this tenant" in missing.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_record_store, None)


def test_memory_api_rejects_cross_tenant_evidence_and_isolates_same_key(
    monkeypatch, tmp_path
):
    database = str(tmp_path / "scientific-memory-tenants.sqlite3")
    store = RecordStore(database)
    source_a = store.create(
        SourceRecord(
            title="Tenant A evidence",
            source_url="https://example.org/a",
            external_identifier=f"a:{uuid4()}",
        ),
        tenant_id="tenant-a",
    )
    source_b = store.create(
        SourceRecord(
            title="Tenant B evidence",
            source_url="https://example.org/b",
            external_identifier=f"b:{uuid4()}",
        ),
        tenant_id="tenant-b",
    )
    monkeypatch.setattr(
        memory_routes,
        "get_settings",
        lambda: SimpleNamespace(database_path=database),
    )
    monkeypatch.setattr(
        records_routes,
        "require_record_access",
        lambda request, action, authorization, x_tenant_id: x_tenant_id,
    )
    app.dependency_overrides[get_record_store] = lambda: store

    try:
        with TestClient(app) as client:
            saved_a = client.post(
                "/api/v1/memory/shared-key",
                headers={"X-Tenant-ID": "tenant-a"},
                json={
                    "value": {"owner": "A"},
                    "evidence_record_ids": [str(source_a.id)],
                },
            )
            assert saved_a.status_code == 201

            cross_tenant = client.post(
                "/api/v1/memory/shared-key",
                headers={"X-Tenant-ID": "tenant-b"},
                json={
                    "value": {"owner": "B but cites A"},
                    "evidence_record_ids": [str(source_a.id)],
                },
            )
            assert cross_tenant.status_code == 422

            saved_b = client.post(
                "/api/v1/memory/shared-key",
                headers={"X-Tenant-ID": "tenant-b"},
                json={
                    "value": {"owner": "B"},
                    "evidence_record_ids": [str(source_b.id)],
                },
            )
            assert saved_b.status_code == 201

            memory_a = client.get(
                "/api/v1/memory/shared-key",
                headers={"X-Tenant-ID": "tenant-a"},
            )
            memory_b = client.get(
                "/api/v1/memory/shared-key",
                headers={"X-Tenant-ID": "tenant-b"},
            )
            assert memory_a.status_code == memory_b.status_code == 200
            assert memory_a.json()["items"][0]["value"] == {"owner": "A"}
            assert memory_b.json()["items"][0]["value"] == {"owner": "B"}
    finally:
        app.dependency_overrides.pop(get_record_store, None)
