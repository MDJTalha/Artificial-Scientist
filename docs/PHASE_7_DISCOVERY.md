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

1. Complete an explicit migration/assignment procedure for legacy NULL-tenant records without guessing ownership.
2. Complete cross-tenant adversarial API tests for every record/discovery/knowledge endpoint and relationship type, including concurrency.
3. Complete production OIDC/JWKS provider and key-rotation evidence.
4. Complete backup/restore and migration rehearsal, sandbox review, and operational controls.
5. Obtain independent security review and release sign-off.

## Scientific-integrity boundaries

- Metadata search is a lead-generation step, not exhaustive systematic review.
- A missing search result does not establish novelty.
- A completeness rubric is not evidence that a hypothesis is true.
- Hypotheses are user-provided structured candidates; the system does not claim autonomous hypothesis generation.
- Experimental outcomes must be independently validated and reproducible.

## Validation

The Phase 7 implementation CI run at commit `ae00a62267451dabf34687c57f8290a690c7bfdc` passed. The isolation-gate changes require their own pull-request CI run before merge.
