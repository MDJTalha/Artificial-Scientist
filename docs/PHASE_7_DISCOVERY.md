# Phase 7 — Hypothesis Discovery, Falsification, and Tenant Isolation

## Scope

Phase 7 provides bounded research-question decomposition, deterministic hypothesis suggestions, structured comparison of competing hypotheses, prior-work metadata screening, and auditable hypothesis-record persistence. It is a research-support workflow, not an autonomous scientific-discovery guarantee.

## Implemented capability

- `POST /api/v1/discovery/decompose` extracts conservative variable/context hints and identifies unresolved details.
- `POST /api/v1/discovery/generate` produces a small positive/inverse/null candidate set from explicitly supplied variables. Suggestions are deterministic, evidence-free, and marked `requires_human_review`.
- `POST /api/v1/discovery/assess` compares competing candidates, checks required structure, records assumptions, alternatives, predictions, falsification criteria, and a discriminating test, and persists hypothesis records atomically with audit events.
- `POST /api/v1/discovery/prior-work-screen` searches bounded OpenAlex/Crossref bibliographic metadata without persisting provider results.
- Source and claim references are validated within the caller's tenant before hypothesis persistence.
- Completeness scoring is a transparent rubric, not a scientific truth or confidence estimate.
- Duplicate detection is a deterministic warning heuristic, not proof of equivalence.
- Request bodies and candidate text are bounded; regression tests cover oversized requests, tenant isolation, and bounded generation.

## Tenant isolation

Research-record, discovery, and knowledge-graph access is tenant-scoped in the integrated main branch. Protected routes require authenticated tenant membership outside development, and caller-supplied evidence references are resolved within the caller's tenant. Legacy ownership migration is explicit and dry-run-first; unknown historical ownership is not guessed.

The repository contains adversarial cross-tenant and concurrency regression coverage. This is repository evidence, not proof of live production identity-provider or deployment behavior.

## Scientific-integrity boundaries

- Metadata search is a lead-generation step, not an exhaustive systematic review.
- A missing search result does not establish novelty.
- A completeness rubric is not evidence that a hypothesis is true.
- Generated candidates are deterministic templates, not model-derived scientific discoveries; they do not claim truth, causality, probability, or novelty.
- Every generated candidate remains subject to prior-work screening, domain constraints, falsification planning, and human review.
- Experimental outcomes must be independently validated and reproducible.

## Release gates

Phase 7 repository acceptance requires the exact current branch SHA to pass frontend type-check/tests/build, Ruff, and the complete backend test suite on Python 3.12 and 3.13.

Production release additionally requires:
1. Real OIDC/JWKS provider and key-rotation evidence.
2. Reviewed migration/backup/restore/recovery rehearsal.
3. Independent security and operational review.
4. Scientific replication, benchmark, and domain-expert evidence.
5. The separate Phase 6 reviewed OS sandbox gate.

No mock test or documentation statement substitutes for those external gates.
