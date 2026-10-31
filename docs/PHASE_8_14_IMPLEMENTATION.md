# Phases 8-14 implementation

This document records the software implementation boundary for the advanced-autonomy stages.

## Phase 8 — Planning and orchestration
Implemented: explicit finite-state workflow, approval gate, checkpoint journal, interruption recovery, failure/cancellation paths, and bounded transitions. Consequential execution cannot transition to RUNNING without an explicit approval token.

## Phase 9 — Analysis and independent verification
Implemented: independent numerical comparison using absolute/relative tolerances and a deterministic bootstrap dispersion check. Non-finite values, length mismatch, and unbounded requests fail closed.

## Phase 10 — Scientific memory
Implemented: immutable version history, source/evidence requirement, content digests, contradiction records, and rollback by creating a new version rather than deleting history.

## Phase 11 — Multi-agent collaboration
Implemented: named specialist roles, bounded task budgets, per-role task limits, independent completed results, and explicit conflict resolution. Consensus is not itself evidence.

## Phase 12 — Scientific writing
Implemented: verified bibliography enforcement, required methods/limitations/data statements, claim limits, and an explicit submission approval gate. No external submission transport is provided.

## Phase 13 — Evaluation and governance
Implemented: versionable benchmark cases, adversarial/security categories, missing-case detection, critical-failure blocking, conditional release for unresolved non-critical issues, and explicit release decisions.

## Phase 14 — Multidisciplinary expansion
Implemented: domain registry with tool allowlists, validation-case requirements, expert-review gates, risk classes, and a hard block on physical actions in this software boundary.

## Cross-phase safety invariant
No phase enables unrestricted agent-generated code execution, bypasses Phase 6 isolation, silently mutates scientific history, treats agreement as evidence, or submits work externally without authorization.

These components are deterministic orchestration primitives. They do not constitute evidence of scientific correctness, production deployment, or expert sign-off. Those remain environment- and reviewer-dependent release gates.
