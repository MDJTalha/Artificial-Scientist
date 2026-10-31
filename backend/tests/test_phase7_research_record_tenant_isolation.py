"""Adversarial tenant-isolation tests for the research-record store."""

from pathlib import Path
from uuid import uuid4

import pytest

from artificial_scientist.records.models import KnowledgeConceptRecord, KnowledgeRelationshipRecord, ResearchTaskRecord, SourceRecord
from artificial_scientist.records.store import InvalidRelationship, RecordNotFound, RecordStore


def test_record_read_list_and_audit_are_isolated(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.sqlite3")
    a = store.create(
        ResearchTaskRecord(title="A task", research_question="Question for tenant A?", objective="A"),
        tenant_id="tenant-a",
    )
    b = store.create(
        ResearchTaskRecord(title="B task", research_question="Question for tenant B?", objective="B"),
        tenant_id="tenant-b",
    )
    assert store.get(a.id, tenant_id="tenant-a").payload["title"] == "A task"
    with pytest.raises(RecordNotFound):
        store.get(a.id, tenant_id="tenant-b")
    items, total = store.list_records(tenant_id="tenant-b")
    assert total == 1 and [item.id for item in items] == [b.id]
    events, event_total = store.list_audit_events(tenant_id="tenant-a")
    assert event_total == 1 and events[0].record_id == a.id


def test_cross_tenant_reference_is_rejected(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.sqlite3")
    source = store.create(
        SourceRecord(title="Private source", source_url="https://example.org/private",
                     external_identifier=f"private:{uuid4()}"),
        tenant_id="tenant-a",
    )
    with pytest.raises(InvalidRelationship, match="not available in this tenant"):
        store.create(
            ResearchTaskRecord(
                title="Cross tenant",
                research_question="Can a tenant reference another tenant?",
                objective="Security regression",
                related_record_ids=[source.id],
            ),
            tenant_id="tenant-b",
        )


def test_source_identity_isolated_between_tenants(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.sqlite3")
    source_a = SourceRecord(
        title="Same identity", source_url="https://example.org/paper",
        external_identifier="doi:10.1000/shared",
    )
    source_b = source_a.model_copy(update={"id": uuid4()})
    store.create(source_a, tenant_id="tenant-a")
    store.create(source_b, tenant_id="tenant-b")
    assert store.list_records(tenant_id="tenant-a")[1] == 1
    assert store.list_records(tenant_id="tenant-b")[1] == 1


def test_knowledge_graph_queries_are_tenant_scoped(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.sqlite3")
    a = store.create(
        KnowledgeConceptRecord(preferred_label="A", definition="Concept A definition."),
        tenant_id="tenant-a",
    )
    b = store.create(
        KnowledgeConceptRecord(preferred_label="B", definition="Concept B definition."),
        tenant_id="tenant-a",
    )
    c = store.create(
        KnowledgeConceptRecord(preferred_label="C", definition="Concept C definition."),
        tenant_id="tenant-b",
    )
    d = store.create(
        KnowledgeConceptRecord(preferred_label="D", definition="Concept D definition."),
        tenant_id="tenant-b",
    )
    store.create(
        KnowledgeRelationshipRecord(source_concept_id=a.id, target_concept_id=b.id, predicate="broader_than"),
        tenant_id="tenant-a",
    )
    store.create(
        KnowledgeRelationshipRecord(source_concept_id=c.id, target_concept_id=d.id, predicate="broader_than"),
        tenant_id="tenant-b",
    )
    edges, total = store.list_knowledge_relationships(concept_id=a.id, tenant_id="tenant-a")
    assert total == 1 and edges[0].payload["target_concept_id"] == str(b.id)
    hidden, hidden_total = store.list_knowledge_relationships(concept_id=c.id, tenant_id="tenant-a")
    assert hidden_total == 0 and hidden == []
