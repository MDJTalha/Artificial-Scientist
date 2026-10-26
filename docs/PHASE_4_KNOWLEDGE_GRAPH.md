# Phase 4 — Scientific Knowledge Graph and Controlled Vocabulary

**Status:** Implementation and acceptance verification in progress.  
**Branch:** \`phase-4-knowledge-graph\`, stacked on \`phase-3-literature-retrieval\`.  
**Design objective:** convert source-traceable research records into a queryable network of scientific concepts and explicitly asserted relationships, without silently merging concepts or treating unreviewed links as established facts.

## Included capability

### Typed concept records

A \`knowledge_concept\` record includes:
- Stable record UUID and content checksum inherited from the common record store.
- Preferred label, definition, alternate labels, language, and controlled concept type.
- Scientific-domain classification and explicit assessment status.
- Optional external identifiers, notes, and links to stored evidence sources.
- Provenance metadata, retained independently from the definition text.

Concepts default to \`proposed\`, not \`active\`. Two concepts may share a preferred label if their definitions or scientific context differ. The store intentionally does not merge concepts based only on similar labels; conflicting definitions remain separate and traceable.

### Controlled vocabulary

The first vocabulary contains concept types such as \`method\`, \`quantity\`, \`equation\`, \`theory\`, \`unit\`, \`algorithm\`, \`model\`, and \`phenomenon\`; initial scientific domains include mathematics, computer science, physics, chemistry, biology, medicine, engineering, earth science, astronomy, social sciences, psychology, economics, materials science, and interdisciplinary research.

Allowed relationship predicates include:
- Hierarchy and classification: \`broader_than\`, \`narrower_than\`, \`subclass_of\`, \`instance_of\`.
- Structure and dependency: \`part_of\`, \`has_part\`, \`prerequisite_of\`, \`requires\`.
- Scientific measurement and method: \`measured_by\`, \`measures\`, \`uses_method\`, \`method_for\`, \`has_unit\`, \`unit_of\`.
- Other explicit links: \`causes\`, \`caused_by\`, \`derived_from\`, \`applied_to\`, \`same_as\`, \`contrasts_with\`, and \`related_to\`.

The list is an initial project vocabulary, not a complete or authoritative global ontology. Adding a predicate to the vocabulary does not establish that the relation holds for any particular concepts.

### Evidence-aware relationship assertions

Every \`knowledge_relationship\` is its own immutable record with a source concept, target concept, controlled predicate, optional evidence-source IDs, an assertion status, optional confidence score, notes, and provenance.

Relationship status values are \`proposed\`, \`source_reported\`, \`reviewed\`, \`disputed\`, and \`rejected\`. A submitted status is an assertion recorded by a caller; the API does not authenticate reviewers or automatically verify the relationship. Rejected assertions remain in history but are excluded from graph-neighborhood traversal. Proposed and disputed edges are shown with their status so clients can avoid treating them as proven.

### Search and graph traversal

- Concept search matches preferred labels, alternate labels, and definition text.
- Optional filters include scientific domain, concept type, and status.
- Search pagination is applied in SQLite after filters rather than over a pre-limited in-memory page.
- The relationship endpoint preserves incoming/outgoing direction and supports predicate filtering.
- Neighborhood traversal is bounded to depths 1–3 and a configurable maximum concept count; the response reports whether it was truncated.
- The graph response preserves the original relationship record, including predicate and assertion status. No inverse edge is automatically inferred.

### Record and relationship integrity

- Both new record types use the existing append-only research-record store, checksum verification, and creation audit events.
- Concept source references must point to existing \`source\` records.
- Relationship endpoints must point to existing \`knowledge_concept\` records; evidence references must point to existing \`source\` records.
- Self-relations are rejected.
- Cycles are rejected for the same asserted hierarchy/part/dependency predicate where that predicate is checked; a rejected assertion does not block a later assertion.
- Every stored relationship is typed and checksum-verified before it contributes to cycle checks or graph responses.
- Database schema version remains 2 because the physical SQLite table structure did not change; the existing record table stores the new versioned record types. New concept/relationship model payloads carry record schema version 1.
- No automatic concept merge, ontology alignment, LLM-generated definition, entity linking, or confidence recalibration occurs in this phase.

## API endpoints

### Vocabulary

\`GET /api/v1/knowledge/vocabulary\`

Returns the controlled concept types, scientific domains, concept statuses, relationship predicates, and assertion statuses.

### Create a concept

\`POST /api/v1/knowledge/concepts\`

\`\`\`json
{
  "preferred_label": "Numerical integration",
  "definition": "A family of methods for approximating definite integrals using numerical procedures.",
  "aliases": ["quadrature"],
  "concept_type": "method",
  "scientific_domain": "mathematics",
  "source_record_ids": [],
  "status": "proposed"
}
\`\`\`

The response contains the concept record ID, server timestamp, content checksum, schema version, and validated payload.

### Search concepts

\`GET /api/v1/knowledge/concepts?query=quadrature&scientific_domain=mathematics&limit=20&offset=0\`

Supported filters: \`query\`, \`scientific_domain\`, \`concept_type\`, \`concept_status\`, \`limit\`, and \`offset\`. Query text matches the preferred label, aliases, or definition. Results do not imply that a concept is correct or that search is semantically exhaustive.

### Add a relationship

\`POST /api/v1/knowledge/relationships\`

\`\`\`json
{
  "source_concept_id": "UUID-OF-AN-EXISTING-CONCEPT",
  "target_concept_id": "UUID-OF-ANOTHER-EXISTING-CONCEPT",
  "predicate": "related_to",
  "assertion_status": "proposed",
  "evidence_source_record_ids": [],
  "notes": "Record the evidence and rationale before making stronger claims."
}
\`\`\`

The placeholder UUIDs above are illustrative only and must be replaced with IDs returned by concept creation.

### Read relationships and neighborhood

- \`GET /api/v1/knowledge/concepts/{concept_id}/relationships?direction=both&predicate=related_to&limit=100\`
- \`GET /api/v1/knowledge/graph/neighborhood?concept_id={uuid}&depth=2&limit=50\`

The neighborhood depth is constrained to 1–3. Traversal is bounded, reports truncation, preserves recorded direction, and excludes rejected edges. It is a graph-view operation, not automatic inference or proof.

## Automated verification strategy

Deterministic tests cover:
- Field validation, alias normalization, and duplicate/primary-label aliases.
- Source provenance and missing/wrong-type references.
- Separate records for ambiguous same-label concepts.
- Search across aliases, labels, definitions, domain/type/status filters, and pagination.
- Relationship endpoint types, direction, status, and evidence source references.
- Self-link rejection and hierarchy-cycle detection.
- Rejected-edge handling in cycle checks.
- Audit entries for new graph record types.
- Vocabulary, concept creation/search, relationship creation, neighborhood traversal, and wrong-type lookups through the API.

## Acceptance criteria

- [ ] Current branch passes Ruff and all backend tests on Python 3.12 and 3.13.
- [ ] Frontend type-check, all frontend tests, and production build pass.
- [ ] Current branch and draft pull-request CI results are reviewed and linked here.
- [ ] Concept search filters and paginates at the database layer.
- [ ] New concept and relationship records retain source references and checksums.
- [ ] Invalid relationship endpoints and self-relations are rejected.
- [ ] Repeated hierarchy/part/dependency links cannot create a checked same-predicate cycle.
- [ ] Same-label concepts remain separate unless a future reviewed resolution workflow explicitly merges them.
- [ ] Graph output exposes relation status and reports bounded traversal truncation.

## Limitations and not implemented

- No ontology imports (such as Wikidata, OBO ontologies, or domain-specific vocabularies) have been integrated yet.
- No equation parser, unit conversion/dimensional analysis, entity linker, vector embeddings, or semantic search model is included.
- The initial domain and predicate list requires expert review before broad use.
- The API is still unauthenticated and intended for localhost development only; do not expose it to an untrusted network.
- Checksums protect stored payload integrity; they do not prove source authenticity, semantic correctness, or reviewer independence.
- A stored edge status is not a certificate of truth. Scientific relationships need external evidence and independent review.
