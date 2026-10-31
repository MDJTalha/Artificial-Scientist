"""Phase 7 tenant-isolation regression tests."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from artificial_scientist.api.routes import records as records_routes
from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.main import app
from artificial_scientist.records.models import ResearchTaskRecord, SourceRecord
from artificial_scientist.records.store import InvalidRelationship, RecordNotFound, RecordStore


def test_records_are_isolated_between_tenants(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.sqlite3")
    first = store.create(
        ResearchTaskRecord(
            title="Tenant A",
            research_question="Question A",
            objective="Objective A",
        ),
        tenant_id="tenant-a",
    )
    second = store.create(
        ResearchTaskRecord(
            title="Tenant B",
            research_question="Question B",
            objective="Objective B",
        ),
        tenant_id="tenant-b",
    )

    assert store.get(first.id, tenant_id="tenant-a").payload["title"] == "Tenant A"
    assert store.get(second.id, tenant_id="tenant-b").payload["title"] == "Tenant B"
    with pytest.raises(RecordNotFound):
        store.get(first.id, tenant_id="tenant-b")
    items, total = store.list_records(tenant_id="tenant-b")
    assert total == 1
    assert [item.id for item in items] == [second.id]


def test_cross_tenant_relationship_is_rejected_without_existence_disclosure(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.sqlite3")
    source = store.create(
        SourceRecord(
            title="Tenant A source",
            source_url="https://example.org/a",
            external_identifier=f"a:{uuid4()}",
        ),
        tenant_id="tenant-a",
    )
    task = ResearchTaskRecord(
        title="Tenant B task",
        research_question="Can cross-tenant references be created?",
        objective="Ensure relationship validation is tenant scoped.",
        related_record_ids=[source.id],
    )
    with pytest.raises(InvalidRelationship, match="not available in this tenant"):
        store.create(task, tenant_id="tenant-b")


def test_same_source_identity_is_allowed_across_tenants(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.sqlite3")
    source_a = SourceRecord(
        title="Same DOI",
        source_url="https://example.org/paper",
        external_identifier="doi:10.1234/shared",
    )
    source_b = source_a.model_copy(update={"id": uuid4()})
    store.create(source_a, tenant_id="tenant-a")
    store.create(source_b, tenant_id="tenant-b")
    assert store.list_records(tenant_id="tenant-a")[1] == 1
    assert store.list_records(tenant_id="tenant-b")[1] == 1


def test_audit_events_are_tenant_scoped(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.sqlite3")
    store.create(
        ResearchTaskRecord(title="A", research_question="A", objective="A"),
        tenant_id="tenant-a",
    )
    store.create(
        ResearchTaskRecord(title="B", research_question="B", objective="B"),
        tenant_id="tenant-b",
    )
    events_a, total_a = store.list_audit_events(tenant_id="tenant-a")
    events_b, total_b = store.list_audit_events(tenant_id="tenant-b")
    assert total_a == total_b == 1
    assert events_a[0].record_id != events_b[0].record_id


def test_api_record_reads_and_discovery_evidence_cannot_cross_tenants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RecordStore(tmp_path / "api-records.sqlite3")
    tenant_a = "tenant-a"
    tenant_b = "tenant-b"
    record_a = store.create(
        ResearchTaskRecord(
            title="Private A",
            research_question="Question A",
            objective="Objective A",
        ),
        tenant_id=tenant_a,
    )
    source_a = store.create(
        SourceRecord(
            title="Private source A",
            source_url="https://example.org/private-a",
            external_identifier=f"a:{uuid4()}",
        ),
        tenant_id=tenant_a,
    )
    store.create(
        ResearchTaskRecord(
            title="Private B",
            research_question="Question B",
            objective="Objective B",
        ),
        tenant_id=tenant_b,
    )

    monkeypatch.setattr(
        records_routes,
        "require_record_access",
        lambda request, action, authorization, x_tenant_id: tenant_b,
    )
    app.dependency_overrides[get_record_store] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/records/{record_a.id}")
            assert response.status_code == 404

            listed = client.get("/api/v1/records")
            assert listed.status_code == 200
            assert listed.json()["total"] == 1
            assert listed.json()["items"][0]["payload"]["title"] == "Private B"

            discovery = client.post(
                "/api/v1/discovery/assess",
                json={
                    "research_question": "Does temperature affect reaction rate?",
                    "candidates": [
                        {
                            "title": "Cross-tenant hypothesis",
                            "statement": "Temperature changes reaction rate.",
                            "assumptions": ["Pressure remains fixed."],
                            "alternative_explanations": ["Catalyst concentration changed."],
                            "predictions": ["Rate changes in the measured range."],
                            "falsification_criteria": ["Rate does not change."],
                            "discriminating_test": "Randomize temperature levels.",
                            "source_record_ids": [str(source_a.id)],
                            "claim_record_ids": [],
                        },
                        {
                            "title": "Independent hypothesis",
                            "statement": "Catalyst concentration changes reaction rate.",
                            "assumptions": ["Temperature remains fixed."],
                            "alternative_explanations": ["Pressure changes."],
                            "predictions": ["Rate tracks catalyst concentration."],
                            "falsification_criteria": ["Rate does not track concentration."],
                            "discriminating_test": "Randomize catalyst concentration.",
                            "source_record_ids": [],
                            "claim_record_ids": [],
                        },
                    ],
                },
            )
            assert discovery.status_code == 422
            assert "does not exist" in discovery.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_record_store, None)


def test_concurrent_tenant_writes_remain_isolated(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "concurrent-records.sqlite3")

    def write(tenant_id: str, index: int) -> None:
        store.create(
            ResearchTaskRecord(
                title=f"{tenant_id}-{index}",
                research_question=f"Question {tenant_id}-{index}",
                objective="Concurrent isolation regression.",
            ),
            tenant_id=tenant_id,
        )

    work = [
        (tenant, index)
        for tenant in ("tenant-a", "tenant-b")
        for index in range(8)
    ]
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda item: write(*item), work))

    items_a, total_a = store.list_records(tenant_id="tenant-a")
    items_b, total_b = store.list_records(tenant_id="tenant-b")
    assert total_a == total_b == 8
    assert {item.payload["title"] for item in items_a} == {
        f"tenant-a-{index}" for index in range(8)
    }
    assert {item.payload["title"] for item in items_b} == {
        f"tenant-b-{index}" for index in range(8)
    }
