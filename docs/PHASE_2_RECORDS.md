# Phase 2 — Research Records and Provenance

**Status:** Acceptance checks passed on implementation commit `48ce326a4402da23ad5787b7eceb82943f2d071f`. See the [passing pull-request CI run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40263258124).  
**Branch:** \`phase-2-research-records\`  
**Design objective:** ensure every research item can be stored, retrieved, related to its evidence, and checked for accidental or out-of-band modification.

## What this phase adds

### Typed record schemas

The backend defines versioned, validated records for:

- Research tasks and bounded research questions.
- Source metadata, URLs, authors, publication/retrieval dates, identifiers, and assessment status.
- Claims, declared evidence status, links to sources/claims/artifacts, and optional confidence estimates.
- Hypotheses, assumptions, alternatives, falsification criteria, and provisional novelty assessments.
- Experiment plans, the hypothesis being tested, variables, controls, success/failure criteria, and declared risk level.
- Experiment runs, plan relationships, declared execution status, environment hashes, seeds, and result artifacts.
- Artifact metadata and content checksums.
- Review records, explicitly treated as submitted review statements rather than proof of reviewer identity or independence.
- Approval requests.

Every record is typed, has a stable UUID, includes schema version 1, and can carry explicit provenance metadata. Unexpected fields are rejected rather than silently accepted.

### Persistence and provenance

The SQLite service stores canonical JSON payloads and a SHA-256 checksum of each payload. It records server-generated creation events in an audit table in the same transaction as the record. The record store is append-only at both API and database-trigger level. A revision should be represented as a new record linked to the earlier one rather than silently rewriting research history.

When reading a record, the service verifies its stored checksum and validates the payload against its declared schema. The database has a schema version marker; a future database version is rejected instead of being silently downgraded.

### Relationship integrity

At creation time, the service checks that referenced records exist and have compatible types. Examples include:

- a claim references source records, related claims, or artifact records;
- a hypothesis references sources and claims, and may supersede an earlier hypothesis;
- an experiment plan references a hypothesis;
- an experiment run references a plan and any output artifacts;
- a review or approval request references an existing target.

Relationship validation is an application-level check within the record creation transaction. It is not a substitute for independent scientific validation.

### API

- \`POST /api/v1/records\` — create a supported typed record.
- \`GET /api/v1/records?record_type=source&limit=20&offset=0\` — list and filter records with bounded pagination.
- \`GET /api/v1/records/{record_id}\` — retrieve a record and verify payload integrity.
- \`GET /api/v1/records/audit-events?limit=20&offset=0\` — read server-generated creation events.

The audit-events path is registered before the UUID path to avoid route ambiguity. Public API calls cannot create, edit, approve, or delete audit events. No record update or delete endpoint is provided.

## Example: create a research task

\`\`\`http
POST /api/v1/records
Content-Type: application/json
\`\`\`

\`\`\`json
{
  "record_type": "research_task",
  "title": "Compare two numerical solvers",
  "research_question": "How do two numerical solvers compare on a defined test equation?",
  "objective": "Run a controlled computational comparison and preserve its configuration."
}
\`\`\`

The response includes a server-assigned creation timestamp, a record UUID, its record type, its validated payload, and a SHA-256 content checksum.

## Example: attach a claim to a source

Create a source record first and save its returned \`id\`. Then submit a claim using that identifier:

\`\`\`json
{
  "record_type": "claim",
  "claim_text": "The source reports the stated numerical convergence result.",
  "evidence_status": "source_reported",
  "source_record_ids": ["UUID-RETURNED-BY-SOURCE-CREATION"]
}
\`\`\`

Use a real UUID returned by the API in practice; the illustrative placeholder above is not a valid UUID.

## Integrity and trust boundaries

- A checksum detects a mismatch between stored payload bytes and the saved digest. It does not prove source authenticity or truth.
- A source record is metadata until a future connector retrieves and verifies it.
- A claim's evidence-status label represents a recorded assessment; it is not an automatic scientific certification.
- A field saying a run is reported completed does not establish that the run occurred. The experiment execution engine is not implemented in this phase.
- Review records do not independently authenticate a human reviewer.
- Approval records are requests only. Their schema does not allow the status \`approved\`.
- This API has no authentication yet and is intended for localhost development only. Do not bind it to an untrusted network.
- No scientific paper, dataset, or artifact is fetched or executed merely because its URI is stored.

## Local configuration

The database defaults to \`data/artificial_scientist.sqlite3\` relative to the backend working directory. Override the location with \`ARTIFICIAL_SCIENTIST_DB_PATH\`. Database files are excluded from version control.

## Verification plan

- [x] Type and field validation rejects malformed/unknown fields.
- [x] Create/get/list/filter/pagination API tests pass.
- [x] Cross-record references reject missing IDs and wrong record types.
- [x] Record and audit-event writes are transactional.
- [x] Data persists across separate store instances.
- [x] Checksum verification detects simulated out-of-band modification.
- [x] Database triggers reject record update and delete.
- [x] Approval requests can be created, but cannot be set to approved through the public record schema.
- [x] Ruff, backend tests on Python 3.12/3.13, frontend tests/type-check/build pass.
- [x] Current CI results are reviewed and linked here.

## Verified CI result

- [Pull-request CI run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40263258124): passed.
- [Push CI run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40263256552): passed.
- Backend: Ruff checks passed; 18 tests passed on Python 3.12 and 18 tests passed on Python 3.13.
- Frontend: TypeScript type-check passed, all 6 unit tests passed, and the production build completed.

## Local backup guidance

The initial store uses a single SQLite database file and does not yet automate backups. For a simple backup, stop the API, copy `data/artificial_scientist.sqlite3` to a protected backup location, verify the copied file can be opened and queried, then restart the API. The configured path may differ when `ARTIFICIAL_SCIENTIST_DB_PATH` is set. For a live-service backup in a later phase, use SQLite's supported backup API and test restoration before schema changes. Backup procedures and backup artifacts must not be committed to the public repository.

## Out of scope

This phase does not implement authentication, multi-user access control, scholarly source ingestion, AI models, a knowledge graph, research orchestration, computation sandboxing, automated scientific validation, or actual approval decisions. These must be designed and tested separately.
