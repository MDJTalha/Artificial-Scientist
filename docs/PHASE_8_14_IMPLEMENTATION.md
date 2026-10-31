# Phases 8-14 implementation

This document records the software implementation boundary for the advanced-autonomy stages.

## Phase 8 — Planning and orchestration

Implemented: explicit finite-state workflow, protected API endpoints, approval gate, checkpoint journal, interruption recovery, failure/cancellation paths, bounded transitions, and SQLite persistence. Consequential execution cannot transition to RUNNING without an explicit approval token. Persistent workflows are tenant-scoped and recoverable across process restart.

## Phase 9 — Analysis and independent verification

Implemented: independent numerical comparison using absolute/relative tolerances and a deterministic bootstrap dispersion check. Non-finite values, length mismatch, and unbounded requests fail closed. The verifier is deliberately independent of the workflow planner and governance decision.

## Phase 10 — Scientific memory

Implemented: immutable version history, source/evidence requirement, content digests, contradiction records, rollback by creating a new version rather than deleting history, SQLite persistence, restart recovery, and tenant-key namespacing.

## Phase 11 — Multi-agent collaboration

Implemented: named specialist roles, bounded task budgets, per-role task limits, independent completed results, explicit conflict handling, and bounded resolution. Consensus is not itself evidence.

## Phase 12 — Scientific writing

Implemented: verified bibliography enforcement, duplicate citation rejection, required methods/limitations/data statements, claim limits, and an explicit submission approval gate. No external submission transport is provided.

## Phase 13 — Evaluation and governance

Implemented: versionable benchmark cases, adversarial/security categories, missing-case detection, critical-failure blocking, conditional release for unresolved non-critical issues, and explicit release decisions. Governance is fail-closed when required benchmark coverage is missing.

## Phase 14 — Multidisciplinary expansion

Implemented: domain registry with bounded domain names, explicit risk classes, non-empty unique tool allowlists, required validation cases, expert-review gates, and a hard block on physical actions in this software boundary. Domain registration rejects malformed or duplicated definitions before they become available. Authorization requires successful validation and expert approval whenever the domain requires it.

The domain registry is intentionally a software governance boundary. It does not certify scientific competence in a domain; every registered domain still needs versioned validation cases and qualified expert review before operational expansion.

## Cross-phase safety invariant

No phase enables unrestricted agent-generated code execution, bypasses Phase 6 isolation, silently mutates scientific history, treats agreement as evidence, or submits work externally without authorization.

## Phase 14 acceptance evidence

The repository tests cover missing validation, missing expert approval, physical-action rejection, malformed domain definitions, duplicate registration, bounded identifiers, and invalid risk classes. The registry does not expose a physical-action transport.

## Integration boundary

Phases 8-14 now have bounded backend primitives, persistent workflow/memory state, a protected workflow API, and regression coverage. They do not independently replace the Phase 6 OS-level sandbox, real OIDC/JWKS verification, production migration/backup rehearsal, or independent security/scientific review. Those are release gates, not claims that can be satisfied by code alone.
