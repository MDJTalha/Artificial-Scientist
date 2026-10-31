# ASDS Artificial Scientist — Current Engineering Status

**Snapshot:** 2026-10-31  
**Repository:** `MDJTalha/Artificial-Scientist`  
**Verified baseline:** `main` commit `b28b6bdaffa4851a2dec390460706e100302d138` is the merged Phase 0/6/7/14 hardening baseline; post-merge CI run 1114 succeeded.

**Release-hardening branch:** `phase-release-verification-hardening` adds the final repository-side authorization matrix, concurrency/race, migration/recovery, frontend accessibility/E2E, release-evidence and documentation controls. The implementation was verified at commit `20681adc2520464a6735628bd0ddf78a3cfa9f61`; GitHub Actions run **1242** (workflow run **41225031000**) passed all backend, frontend and release-gate jobs. Subsequent branch commits are documentation-only evidence synchronization.

This document is the current repository evidence snapshot. Older phase documents may contain historical branch names or earlier implementation descriptions; this snapshot takes precedence for the present integration state.

## Verified integration state

### Main branch

The current `main` head contains:
- the reconciled Phases 8–14 bounded-autonomy implementation;
- tenant-scoped Phase 7 research-record and knowledge-graph controls;
- Phase 6 controlled-lab authorization, quotas, recovery, artifacts, retention, audit and execution controls;
- the fail-closed Phase 6 execution-adapter boundary.

### Latest main CI

GitHub Actions run **41212896349** (run number **1114**) for commit `b28b6bdaffa4851a2dec390460706e100302d138` completed with **success**. It verifies Python 3.12, Python 3.13, frontend type-check/tests/build on the merged Phase 0/6/7/14 hardening baseline.

The repository CI workflow covers:
- Python 3.12 backend checks/tests;
- Python 3.13 backend checks/tests;
- frontend type-check, unit tests, production build and release E2E/accessibility on the release-hardening branch.

A successful CI result is repository evidence only. It is not evidence of production deployment, live identity-provider validation, OS sandbox certification, scientific validity, or independent security review.

## Phase status

| Phase | Repository status | Release interpretation |
|---|---|---|
| 0 | Repository baseline complete | External review/evaluation evidence remains environment-dependent |
| 1 | Integrated | Repository implementation complete; operational setup remains environment-dependent |
| 2 | Integrated | Provenance implementation exists; long-term backup/data-governance evidence remains operational |
| 3 | Integrated | Retrieval implementation exists; provider availability/licensing remain deployment concerns |
| 4 | Integrated | Knowledge graph implementation exists; scientific-definition conflicts require evidence review |
| 5 | Integrated | Bounded scientific tools are implemented; tool correctness remains benchmark/evaluation dependent |
| 6 | Hardened, **not release-complete** | Real OS-level sandbox, live IdP verification, migration rehearsal, operations validation and independent review remain open |
| 7 | Implemented, **acceptance-gated** | Tenant isolation, legacy ownership migration and discovery structure are integrated; scientific novelty/truth/expert validation remain evidence-gated |
| 8 | Implemented | Bounded workflow, approval, persistence and recovery are integrated |
| 9 | Implemented | Independent verification primitives are integrated; broader benchmark evidence remains required |
| 10 | Implemented | Versioned tenant-scoped memory and contradiction/rollback semantics are integrated |
| 11 | Implemented | Bounded roles, budgets and conflict resolution are integrated |
| 12 | Implemented | Evidence-linked writing and explicit submission authorization are integrated |
| 13 | Implemented | Governance and benchmark decision primitives are integrated; external review remains required |
| 14 | Hardened implementation with hard physical-action boundary | Domain expansion remains evidence- and expert-gated; registry controls and adversarial definition tests are integrated |

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

## Repository-side final verification

The previously open repository-side hardening items are implemented on `phase-release-verification-hardening`:

- endpoint-by-endpoint authorization contract and cross-tenant adversarial coverage;
- atomic quota and ownership race regressions;
- migration/recovery source-integrity and rollback assertions;
- conference-grade frontend Playwright keyboard/navigation and automated accessibility checks;
- machine-readable release policy and populated evidence matrix;
- synchronized status/evidence documentation.

These items are **repository-verified** by CI run **1242** against implementation commit `20681adc2520464a6735628bd0ddf78a3cfa9f61`: Python 3.12/3.13 backend tests and Ruff, frontend type-check/unit/build, Playwright/axe E2E, and the targeted release-gate suites all passed.

The remaining open items are external certification gates listed above and are intentionally not represented as complete by repository changes. See `docs/release/EVIDENCE_MATRIX.md` for the evidence register.
