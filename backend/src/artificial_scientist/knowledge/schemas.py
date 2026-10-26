"""Response schemas for the scientific knowledge graph API."""

from pydantic import BaseModel, Field

from artificial_scientist.records.models import RecordEnvelope


class KnowledgeConceptSearchResponse(BaseModel):
    items: list[RecordEnvelope]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class KnowledgeRelationshipListResponse(BaseModel):
    items: list[RecordEnvelope]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class KnowledgeGraphNeighborhoodResponse(BaseModel):
    root: RecordEnvelope
    nodes: list[RecordEnvelope]
    relationships: list[RecordEnvelope]
    depth: int = Field(ge=1, le=3)
    truncated: bool
    note: str = (
        "Graph edges are recorded assertions. Proposed or disputed links are not facts, "
        "and rejected relationships are excluded from neighborhood traversal."
    )


class KnowledgeVocabularyResponse(BaseModel):
    concept_types: list[str]
    scientific_domains: list[str]
    concept_statuses: list[str]
    relationship_predicates: list[str]
    relationship_statuses: list[str]
    note: str = (
        "This is the project's initial controlled vocabulary, not a complete or "
        "authoritative global ontology. Terms may require domain-expert review."
    )
