"""Tests for scientific concepts, controlled vocabulary, and graph traversal."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.main import app
from artificial_scientist.records.models import (
    KnowledgeConceptRecord,
    KnowledgeRelationshipRecord,
    SourceRecord,
)
from artificial_scientist.records.store import InvalidRelationship, RecordStore


@pytest.fixture
def store(tmp_path: Path) -> RecordStore:
    return RecordStore(tmp_path / "knowledge.sqlite3")


def concept(
    label: str,
    *,
    domain: str = "mathematics",
    aliases: list[str] | None = None,
    sources: list | None = None,
) -> KnowledgeConceptRecord:
    return KnowledgeConceptRecord(
        preferred_label=label,
        definition=f"{label} is a scientific concept recorded for research and explanation.",
        aliases=aliases or [],
        concept_type="method",
        scientific_domain=domain,
        source_record_ids=sources or [],
    )


def relation(
    source_id,
    target_id,
    predicate: str = "related_to",
    *,
    status: str = "proposed",
    sources: list | None = None,
) -> KnowledgeRelationshipRecord:
    return KnowledgeRelationshipRecord(
        source_concept_id=source_id,
        target_concept_id=target_id,
        predicate=predicate,
        assertion_status=status,
        evidence_source_record_ids=sources or [],
    )


def test_concept_aliases_are_normalized_and_must_be_unique() -> None:
    record = concept("Numerical integration", aliases=["quadrature", "area rule"])
    assert record.aliases == ["quadrature", "area rule"]

    with pytest.raises(ValidationError, match="aliases must be unique"):
        concept("Numerical integration", aliases=["Quadrature", "quadrature"])

    with pytest.raises(ValidationError, match="distinct from the preferred label"):
        concept("Numerical integration", aliases=["numerical integration"])


def test_concept_and_provenance_reference_a_stored_source(store: RecordStore) -> None:
    source = store.create(
        SourceRecord(
            title="Numerical methods reference",
            source_url="https://example.org/numerical-methods",
            external_identifier="manual:test:source",
        )
    )
    saved = store.create(
        concept("Numerical integration", aliases=["quadrature"], sources=[source.id])
    )

    assert saved.record_type == "knowledge_concept"
    persisted = store.get(saved.id)
    assert persisted.payload["source_record_ids"] == [str(source.id)]
    assert persisted.payload["status"] == "proposed"
    assert persisted.payload["provenance"]["method"] == "human_provided"


def test_missing_and_wrong_type_source_references_are_rejected(
    store: RecordStore,
) -> None:
    with pytest.raises(InvalidRelationship, match="does not exist"):
        store.create(concept("Missing citation", sources=[uuid4()]))

    non_source = store.create(concept("Not a source record"))
    with pytest.raises(InvalidRelationship, match="expects record type"):
        store.create(concept("Incorrect evidence type", sources=[non_source.id]))


def test_same_label_with_different_definitions_is_not_silently_merged(
    store: RecordStore,
) -> None:
    first = concept("Model", domain="computer_science")
    second = KnowledgeConceptRecord(
        preferred_label="Model",
        definition="A different model concept with a distinct context and definition.",
        concept_type="theory",
        scientific_domain="mathematics",
    )

    saved_first = store.create(first)
    saved_second = store.create(second)

    assert saved_first.id != saved_second.id
    assert store.get(saved_first.id).payload["definition"] != store.get(
        saved_second.id
    ).payload["definition"]
    _, total = store.search_knowledge_concepts(query="model")
    assert total == 2


def test_concept_search_includes_aliases_definitions_and_filters(
    store: RecordStore,
) -> None:
    store.create(
        concept(
            "Gaussian quadrature",
            aliases=["Gauss integration"],
            domain="mathematics",
        )
    )
    store.create(
        concept("Neural network", aliases=["artificial neural system"], domain="computer_science")
    )
    store.create(concept("Finite element method", domain="engineering"))

    alias_hits, alias_total = store.search_knowledge_concepts(query="artificial neural")
    assert alias_total == 1
    assert alias_hits[0].payload["preferred_label"] == "Neural network"

    domain_hits, domain_total = store.search_knowledge_concepts(
        scientific_domain="engineering",
        concept_type="method",
    )
    assert domain_total == 1
    assert domain_hits[0].payload["preferred_label"] == "Finite element method"

    page, total = store.search_knowledge_concepts(limit=1, offset=1)
    assert total == 3
    assert len(page) == 1


def test_create_and_list_relationships_preserves_direction_and_status(
    store: RecordStore,
) -> None:
    broad = store.create(concept("Numerical method"))
    narrow = store.create(concept("Numerical integration"))
    edge = store.create(
        relation(
            broad.id,
            narrow.id,
            "broader_than",
            status="source_reported",
        )
    )

    outgoing, outgoing_total = store.list_knowledge_relationships(
        concept_id=broad.id,
        direction="outgoing",
    )
    incoming, incoming_total = store.list_knowledge_relationships(
        concept_id=narrow.id,
        direction="incoming",
    )
    assert outgoing_total == incoming_total == 1
    assert outgoing[0].id == incoming[0].id == edge.id
    assert outgoing[0].payload["source_concept_id"] == str(broad.id)
    assert outgoing[0].payload["target_concept_id"] == str(narrow.id)
    assert outgoing[0].payload["assertion_status"] == "source_reported"


def test_relationship_requires_existing_concepts_and_optional_source_evidence(
    store: RecordStore,
) -> None:
    first = store.create(concept("First concept"))
    second = store.create(concept("Second concept"))
    with pytest.raises(InvalidRelationship, match="does not exist"):
        store.create(relation(first.id, uuid4()))

    source = store.create(
        SourceRecord(
            title="Evidence source",
            source_url="https://example.org/evidence",
            external_identifier="manual:evidence:1",
        )
    )
    saved = store.create(
        relation(first.id, second.id, "related_to", sources=[source.id])
    )
    assert saved.payload["evidence_source_record_ids"] == [str(source.id)]


def test_self_relationships_and_hierarchy_cycles_are_rejected(store: RecordStore) -> None:
    first = store.create(concept("Parent concept"))
    second = store.create(concept("Child concept"))
    third = store.create(concept("Grandchild concept"))

    with pytest.raises(InvalidRelationship, match="itself"):
        store.create(relation(first.id, first.id))

    store.create(relation(first.id, second.id, "broader_than"))
    store.create(relation(second.id, third.id, "broader_than"))
    with pytest.raises(InvalidRelationship, match="create a cycle"):
        store.create(relation(third.id, first.id, "broader_than"))


def test_rejected_hierarchy_assertion_does_not_create_active_cycle(
    store: RecordStore,
) -> None:
    first = store.create(concept("Concept alpha"))
    second = store.create(concept("Concept beta"))
    store.create(relation(first.id, second.id, "broader_than", status="rejected"))
    store.create(relation(second.id, first.id, "broader_than", status="source_reported"))


def test_record_created_audit_event_supports_graph_record_types(store: RecordStore) -> None:
    item = store.create(concept("Audit graph node"))
    events, total = store.list_audit_events()

    assert total == 1
    event = next(event for event in events if event.record_id == item.id)
    assert event.record_type == "knowledge_concept"
    assert event.content_sha256 == item.content_sha256


def test_knowledge_api_creates_searches_and_traverses_graph(
    store: RecordStore,
) -> None:
    app.dependency_overrides[get_record_store] = lambda: store
    try:
        with TestClient(app) as client:
            vocabulary = client.get("/api/v1/knowledge/vocabulary")
            assert vocabulary.status_code == 200
            vocabulary_body = vocabulary.json()
            assert "equation" in vocabulary_body["concept_types"]
            assert "broader_than" in vocabulary_body["relationship_predicates"]

            first_response = client.post(
                "/api/v1/knowledge/concepts",
                json={
                    "preferred_label": "Scientific method",
                    "definition": "A systematic process used for scientific investigation.",
                    "aliases": ["research method"],
                    "concept_type": "method",
                    "scientific_domain": "interdisciplinary",
                },
            )
            second_response = client.post(
                "/api/v1/knowledge/concepts",
                json={
                    "preferred_label": "Experimental design",
                    "definition": "A planned arrangement of scientific experiments and controls.",
                    "concept_type": "method",
                    "scientific_domain": "engineering",
                },
            )
            assert first_response.status_code == 201
            assert second_response.status_code == 201
            first = first_response.json()
            second = second_response.json()

            edge_response = client.post(
                "/api/v1/knowledge/relationships",
                json={
                    "source_concept_id": first["id"],
                    "target_concept_id": second["id"],
                    "predicate": "related_to",
                    "assertion_status": "proposed",
                },
            )
            assert edge_response.status_code == 201

            search = client.get(
                "/api/v1/knowledge/concepts",
                params={"query": "research method", "limit": 10},
            )
            assert search.status_code == 200
            assert search.json()["total"] == 1
            assert search.json()["items"][0]["id"] == first["id"]

            neighborhood = client.get(
                "/api/v1/knowledge/graph/neighborhood",
                params={"concept_id": first["id"], "depth": 1},
            )
            assert neighborhood.status_code == 200
            body = neighborhood.json()
            assert len(body["nodes"]) == 2
            assert len(body["relationships"]) == 1
            assert body["truncated"] is False

            outgoing = client.get(
                f"/api/v1/knowledge/concepts/{first['id']}/relationships",
                params={"direction": "outgoing", "predicate": "related_to"},
            )
            assert outgoing.status_code == 200
            assert outgoing.json()["total"] == 1
    finally:
        app.dependency_overrides.clear()


def test_knowledge_api_rejects_invalid_predicate_and_non_concept_id(
    store: RecordStore,
) -> None:
    app.dependency_overrides[get_record_store] = lambda: store
    try:
        with TestClient(app) as client:
            invalid = client.post(
                "/api/v1/knowledge/relationships",
                json={
                    "source_concept_id": str(uuid4()),
                    "target_concept_id": str(uuid4()),
                    "predicate": "invented_scientific_relation",
                },
            )
            assert invalid.status_code == 422

            ordinary = store.create(
                SourceRecord(
                    title="Ordinary source",
                    source_url="https://example.org/ordinary",
                )
            )
            response = client.get(f"/api/v1/knowledge/concepts/{ordinary.id}")
            assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
