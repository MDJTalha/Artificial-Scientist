"""Phase 7 tenant-isolation regression tests."""

from pathlib import Path
from uuid import uuid4

import pytest

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
