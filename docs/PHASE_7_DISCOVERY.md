# Phase 7 — Hypothesis Discovery and Isolation Gate

## Scope

Phase 7 provides bounded research-question decomposition, structured comparison of competing hypotheses, prior-work metadata screening, and auditable hypothesis-record persistence. It is a research-support workflow, not an autonomous scientific-discovery guarantee.

## Implemented capability

- `POST /api/v1/discovery/decompose` extracts conservative variable/context hints and identifies unresolved details.
- `POST /api/v1/discovery/assess` compares 2–10 candidates, checks required structure, records assumptions, alternatives, predictions, falsification criteria, and a discriminating test, and persists hypothesis records atomically with audit events.
- `POST /api/v1/discovery/prior-work-screen` searches bounded OpenAlex/Crossref bibliographic metadata without persisting provider results.
- Source and claim references are validated before hypothesis persistence.
- Completeness scoring is a transparent rubric, not a scientific truth or confidence estimate.
- Duplicate detection is a deterministic warning heuristic, not proof of equivalence.
- Request bodies and candidate text are bounded; regression tests cover oversize requests and legacy payload checksums.

## Release isolation gate

The general research-record store is append-only but is not yet tenant-scoped. Phase 6 tenant authorization currently protects lab runs and artifacts; it does not isolate general research records. A caller could otherwise read or reference shared research records across tenant boundaries.

To fail safely, `Phase7RecordIsolationGateMiddleware` returns HTTP 503 with `Cache-Control: no-store` for `/api/v1/records` and `/api/v1/discovery/*` whenever `ARTIFICIAL_SCIENTIST_ENV` is not `development`. This is a release gate, not a substitute for tenant-scoped authorization. Local development and tests remain available.

**Do not mark Phase 7 production-ready until all of the following are completed and independently reviewed:**

1. Add immutable tenant ownership to research records and audit events with a migration plan for existing records.
2. Scope create, get, list, search, graph traversal, evidence-reference validation, duplicate checks, and audit queries by the authorized tenant.
3. Verify that cross-tenant record IDs and relationship references cannot disclose record existence or content.
4. Authenticate discovery and record endpoints using the configured OIDC trust, require active membership, and apply a least-privilege action matrix.
5. Add adversarial cross-tenant tests for every endpoint and every relationship type, including concurrent requests and migration/backfill behavior.
6. Complete production OIDC/JWKS verification, backup/restore rehearsal, sandbox review, and operational controls.

## Scientific-integrity boundaries

- Metadata search is a lead-generation step, not exhaustive systematic review.
- A missing search result does not establish novelty.
- A completeness rubric is not evidence that a hypothesis is true.
- Hypotheses are user-provided structured candidates; the system does not claim autonomous hypothesis generation.
- Experimental outcomes must be independently validated and reproducible.

## Validation

The Phase 7 implementation CI run at commit `ae00a62267451dabf34687c57f8290a690c7bfdc` passed. The isolation-gate changes require their own pull-request CI run before merge.
