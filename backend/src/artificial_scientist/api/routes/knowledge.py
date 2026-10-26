"""API endpoints for the source-traceable scientific knowledge graph."""

from collections import deque
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.knowledge.schemas import (
    KnowledgeConceptSearchResponse,
    KnowledgeGraphNeighborhoodResponse,
    KnowledgeRelationshipListResponse,
    KnowledgeVocabularyResponse,
)
from artificial_scientist.records.models import (
    CONCEPT_STATUSES,
    CONCEPT_TYPES,
    KNOWLEDGE_PREDICATES,
    RELATIONSHIP_STATUSES,
    SCIENTIFIC_DOMAINS,
    ConceptStatus,
    ConceptType,
    KnowledgeConceptRecord,
    KnowledgePredicate,
    KnowledgeRelationshipRecord,
    RecordEnvelope,
    ScientificDomain,
)
from artificial_scientist.records.store import (
    DuplicateSource,
    InvalidRelationship,
    RecordConflict,
    RecordIntegrityError,
    RecordNotFound,
    RecordStore,
    RecordStoreError,
)

router = APIRouter(prefix="/api/v1/knowledge", tags=["scientific knowledge graph"])


def _translate_error(error: RecordStoreError) -> HTTPException:
    if isinstance(error, (RecordConflict, DuplicateSource)):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, InvalidRelationship):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, RecordNotFound):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, RecordIntegrityError):
        return HTTPException(
            status_code=500,
            detail="Stored record failed integrity verification.",
        )
    return HTTPException(
        status_code=500,
        detail="The knowledge graph operation failed.",
    )


def _get_concept(store: RecordStore, concept_id: UUID) -> RecordEnvelope:
    try:
        envelope = store.get(concept_id)
    except RecordStoreError as error:
        raise _translate_error(error) from error
    if envelope.record_type != "knowledge_concept":
        raise HTTPException(status_code=404, detail="Knowledge concept was not found.")
    return envelope


@router.get("/vocabulary", response_model=KnowledgeVocabularyResponse)
def get_vocabulary() -> KnowledgeVocabularyResponse:
    """Return the controlled vocabulary currently supported by this version."""
    return KnowledgeVocabularyResponse(
        concept_types=list(CONCEPT_TYPES),
        scientific_domains=list(SCIENTIFIC_DOMAINS),
        concept_statuses=list(CONCEPT_STATUSES),
        relationship_predicates=list(KNOWLEDGE_PREDICATES),
        relationship_statuses=list(RELATIONSHIP_STATUSES),
    )


@router.post(
    "/concepts",
    response_model=RecordEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def create_concept(
    record: KnowledgeConceptRecord,
    store: Annotated[RecordStore, Depends(get_record_store)],
) -> RecordEnvelope:
    """Add an immutable concept without merging it into similarly named concepts."""
    try:
        return store.create(record)
    except RecordStoreError as error:
        raise _translate_error(error) from error


@router.get("/concepts", response_model=KnowledgeConceptSearchResponse)
def search_concepts(
    store: Annotated[RecordStore, Depends(get_record_store)],
    query: str | None = Query(default=None, min_length=2, max_length=200),
    scientific_domain: ScientificDomain | None = Query(default=None),
    concept_type: ConceptType | None = Query(default=None),
    concept_status: ConceptStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> KnowledgeConceptSearchResponse:
    """Search labels, aliases and definitions with server-side pagination."""
    try:
        items, total = store.search_knowledge_concepts(
            query=query,
            scientific_domain=scientific_domain,
            concept_type=concept_type,
            concept_status=concept_status,
            limit=limit,
            offset=offset,
        )
    except RecordStoreError as error:
        raise _translate_error(error) from error
    return KnowledgeConceptSearchResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/concepts/{concept_id}", response_model=RecordEnvelope)
def get_concept(
    concept_id: UUID,
    store: Annotated[RecordStore, Depends(get_record_store)],
) -> RecordEnvelope:
    """Fetch a concept and verify its content checksum and schema."""
    return _get_concept(store, concept_id)


@router.post(
    "/relationships",
    response_model=RecordEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    record: KnowledgeRelationshipRecord,
    store: Annotated[RecordStore, Depends(get_record_store)],
) -> RecordEnvelope:
    """Create a typed, evidence-linkable relationship between two existing concepts."""
    try:
        return store.create(record)
    except RecordStoreError as error:
        raise _translate_error(error) from error


@router.get(
    "/concepts/{concept_id}/relationships",
    response_model=KnowledgeRelationshipListResponse,
)
def list_concept_relationships(
    concept_id: UUID,
    store: Annotated[RecordStore, Depends(get_record_store)],
    direction: Literal["incoming", "outgoing", "both"] = Query(default="both"),
    predicate: KnowledgePredicate | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> KnowledgeRelationshipListResponse:
    """Read a concept's incoming/outgoing assertions without inferring inverse edges."""
    _get_concept(store, concept_id)
    try:
        items, total = store.list_knowledge_relationships(
            concept_id=concept_id,
            direction=direction,
            predicate=predicate,
            limit=limit,
            offset=offset,
        )
    except RecordStoreError as error:
        raise _translate_error(error) from error
    return KnowledgeRelationshipListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/graph/neighborhood", response_model=KnowledgeGraphNeighborhoodResponse)
def get_graph_neighborhood(
    store: Annotated[RecordStore, Depends(get_record_store)],
    concept_id: UUID,
    depth: int = Query(default=1, ge=1, le=3),
    limit: int = Query(default=50, ge=1, le=100),
) -> KnowledgeGraphNeighborhoodResponse:
    """Traverse a bounded neighborhood without executing or interpreting source content."""
    root = _get_concept(store, concept_id)
    nodes: dict[UUID, RecordEnvelope] = {concept_id: root}
    relationships: dict[UUID, RecordEnvelope] = {}
    frontier: deque[UUID] = deque([concept_id])
    visited: set[UUID] = {concept_id}
    truncated = False
    edge_limit = min(200, limit * 2)

    for _ in range(depth):
        next_frontier: deque[UUID] = deque()
        while frontier:
            current_id = frontier.popleft()
            try:
                edges, total = store.list_knowledge_relationships(
                    concept_id=current_id,
                    direction="both",
                    limit=100,
                )
            except RecordStoreError as error:
                raise _translate_error(error) from error
            if total > len(edges):
                truncated = True

            for edge in edges:
                if edge.payload.get("assertion_status") == "rejected":
                    continue
                if edge.id not in relationships and len(relationships) >= edge_limit:
                    truncated = True
                    break
                relationships.setdefault(edge.id, edge)
                source_id = UUID(str(edge.payload["source_concept_id"]))
                target_id = UUID(str(edge.payload["target_concept_id"]))
                neighbor_id = target_id if source_id == current_id else source_id

                if neighbor_id in visited:
                    continue
                if len(nodes) >= limit:
                    truncated = True
                    continue
                try:
                    neighbor = store.get(neighbor_id)
                except RecordNotFound:
                    continue
                except RecordStoreError as error:
                    raise _translate_error(error) from error
                if neighbor.record_type != "knowledge_concept":
                    continue
                nodes[neighbor_id] = neighbor
                visited.add(neighbor_id)
                next_frontier.append(neighbor_id)

                if len(relationships) >= edge_limit:
                    truncated = True
                    break
            if len(relationships) >= edge_limit:
                break
        frontier = next_frontier
        if not frontier or len(relationships) >= edge_limit:
            break

    return KnowledgeGraphNeighborhoodResponse(
        root=root,
        nodes=list(nodes.values()),
        relationships=list(relationships.values()),
        depth=depth,
        truncated=truncated,
    )
