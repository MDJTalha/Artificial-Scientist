# ASDS Artificial Scientist — Current Engineering Status

**Snapshot:** 2026-10-31  
**Repository:** `MDJTalha/Artificial-Scientist`  
**Current `main` commit:** `5c645834ef2895ab90404099073d312faee2a0e7`

This document is the current repository evidence snapshot. Older phase documents may contain historical branch names or earlier implementation descriptions; this snapshot takes precedence for the present integration state.

## Verified integration state

### Main branch

The current `main` head contains:
- the reconciled Phases 8–14 bounded-autonomy implementation;
- tenant-scoped Phase 7 research-record and knowledge-graph controls;
- Phase 6 controlled-lab authorization, quotas, recovery, artifacts, retention, audit and execution controls;
- the fail-closed Phase 6 execution-adapter boundary.

### Latest main CI

GitHub Actions run **41209898005** (run number **1077**) for commit `5c645834ef2895ab90404099073d312faee2a0e7` completed with **success**.

The repository CI workflow covers:
- Python 3.12 backend checks/tests;
- Python 3.13 backend checks/tests;
- frontend type-check, unit tests and production build.

A successful CI result is repository evidence only. It is not evidence of production deployment, live identity-provider validation, OS sandbox certification, scientific validity, or independent security review.

## Phase status

| Phase | Repository status | Release interpretation |
|---|---|---|
| 0 | Foundation substantially documented | Risk/evaluation baseline still requires formal completion |
| 1 | Integrated | Repository implementation complete; operational setup remains environment-dependent |
| 2 | Integrated | Provenance implementation exists; long-term backup/data-governance evidence remains operational |
| 3 | Integrated | Retrieval implementation exists; provider availability/licensing remain deployment concerns |
| 4 | Integrated | Knowledge graph implementation exists; scientific-definition conflicts require evidence review |
| 5 | Integrated | Bounded scientific tools are implemented; tool correctness remains benchmark/evaluation dependent |
| 6 | Advanced, **not release-complete** | Real OS-level sandbox, live IdP verification, migration rehearsal, operations validation and independent review remain open |
| 7 | Implemented, **acceptance-gated** | Tenant isolation and discovery structure exist; novelty/truth/expert validation are not claimed |
| 8 | Implemented | Bounded workflow, approval, persistence and recovery are integrated |
| 9 | Implemented | Independent verification primitives are integrated; broader benchmark evidence remains required |
| 10 | Implemented | Versioned tenant-scoped memory and contradiction/rollback semantics are integrated |
| 11 | Implemented | Bounded roles, budgets and conflict resolution are integrated |
| 12 | Implemented | Evidence-linked writing and explicit submission authorization are integrated |
| 13 | Implemented | Governance and benchmark decision primitives are integrated; external review remains required |
| 14 | Implemented with hard physical-action boundary | Domain expansion remains evidence- and expert-gated |

## Phase 6 security boundary

Production-like lab execution now resolves through an explicit adapter. The trusted local subprocess runner is available only when the application environment is explicitly set to development with local-process mode.

For production-like environments:
- no implicit subprocess fallback exists;
- an undeployed `sandbox:<name>` adapter remains unavailable by design;
- missing reviewed sandbox configuration fails closed;
- the API reports HTTP 503 rather than executing inside the service host.

This is a security hardening measure, not a claim that the repository contains a production OS sandbox.

## Remaining external release gates

These cannot honestly be completed by repository edits alone:

1. **Reviewed OS sandbox deployment:** select a target runtime and prove filesystem, network, syscall/capability, identity, resource, artifact and cleanup controls with adversarial tests.
2. **Real OIDC/JWKS verification:** validate against the actual provider, including rotation/unknown-key refresh and provider-specific claims.
3. **Production migration/recovery rehearsal:** use a sanitized representative snapshot and verify backup, restore, WAL/recovery, migration, rollback and ownership reconciliation.
4. **Independent security review:** review authentication, tenant isolation, audit integrity/retention, quotas, secrets, dependencies and deployment configuration.
5. **Operational deployment validation:** TLS, secret management, least privilege, monitoring, alerting, rate limiting, incident response and backup/restore.
6. **Scientific evaluation:** benchmark validity, replication, domain-expert review, misleading-source/prompt-injection resistance and scientific-integrity assessment.

## Engineering rule

No external gate is marked complete merely because a unit test, mock provider, documentation page, or CI run exists. The release package must contain concrete evidence, scope, commit/version, commands, outcomes, limitations, risks and sign-off for every gate.

## Next repository-side priorities

While external evidence is being gathered, repository work should continue on:
- endpoint-by-endpoint authorization and cross-tenant negative-test coverage;
- concurrency/race regressions for quotas and ownership;
- migration/rehearsal fixture quality and rollback assertions;
- frontend accessibility/E2E and conference-grade research-workspace verification;
- CI/release-gate automation that prevents stale documentation from being interpreted as production certification.
