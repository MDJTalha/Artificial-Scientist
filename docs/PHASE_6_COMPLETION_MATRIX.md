# Phase 6 — Completion and Release-Gate Matrix

**Integrated branch:** main (`5c645834ef2895ab90404099073d312faee2a0e7`)  
**Scope:** tenant-aware controlled computational lab, identity, authorization, quotas, audit, migration safety, and process-execution controls.

This matrix is the repository-side checklist for Phase 6. “Implemented” means code and regression coverage exist in the integrated main branch; it does not mean production deployment, independent security assurance, or a full operating-system sandbox has been certified.

## Implementation checklist

| Area | Implemented control | Regression / evidence |
|---|---|---|
| OIDC identity | RS256-only validation; configured issuer/audience; required expiry, issued-at, issuer, audience, subject claims; no leeway; bounded subject/issuer; strict HTTPS JWKS URL checks; controlled validation errors | backend/tests/test_identity.py |
| OIDC trust boundary | Partial OIDC configuration fails closed; legacy API key cannot bypass configured OIDC | backend/tests/test_identity_api.py |
| Tenant directory | Opaque stable principal/tenant IDs; explicit tenant records and active memberships; role/action allowlist; deny-by-default | backend/src/artificial_scientist/authorization.py and authorization tests |
| Object isolation | Tenant-scoped run, execution-status, JSON artifact, binary artifact, export, and verification access; cross-tenant IDs are not sufficient authorization | backend/tests/test_identity_api.py, store and artifact tests |
| Audit | Request outcome events, correlation IDs, anonymous auth-failure events, denied object-access records, bounded metadata, fail-closed response if final audit persistence fails | backend/tests/test_identity_api.py |
| Tenant quotas | Transaction-protected tenant run, JSON artifact, binary artifact count and byte budgets; HTTP 429 on run quota exhaustion | backend/tests/test_tenant_scoped_store.py, test_tenant_binary_artifacts.py, test_identity_api.py |
| Binary uploads | Header and streaming size caps, canonical ASCII decimal Content-Length, filename/media-type validation, non-empty content, cross-tenant denial before scan, scanner fail-closed behavior | backend/tests/test_lab.py, backend/tests/test_identity_api.py |
| Scanner boundary | Invalid ClamAV response encoding is rejected as scanner unavailable | backend/tests/test_lab.py |
| Worker isolation | Spawned allowlisted worker, finite positive timeout, POSIX CPU/address-space/file-size/open-file/core limits where supported, terminate-then-kill cleanup, pipe closure, bounded worker error, controlled handling of abrupt child exit | backend/src/artificial_scientist/lab/execution.py, backend/tests/test_lab.py |\n| Execution boundary selection | Deployment-neutral adapter interface; local subprocess mode is development-only; production-like environments fail closed when no reviewed OS sandbox adapter is configured | backend/src/artificial_scientist/lab/execution_adapter.py, backend/tests/test_lab.py |
| Tenant-aware recovery | Interrupted attempts reconcile only against a run with matching tenant ownership | backend/tests/test_tenant_execution_attempts.py |
| Legacy ownership | Explicit manifest only; dry-run by default; UUID and duplicate validation; existing tenant/run checks; conflicting ownership aborts atomically; operator principal required for apply; audit written in transaction | backend/src/artificial_scientist/records/legacy_claim.py, backend/tests/test_phase7_legacy_claim.py |
| Migration rehearsal | Consistent SQLite snapshot, dry-run, apply to temporary copy only, ownership and operator-audit verification; source remains unclaimed | backend/src/artificial_scientist/phase6_rehearsal.py, backend/tests/test_phase6_rehearsal.py |
| Legacy schema safety | Additive schema migration leaves unknown historical ownership unassigned and tenant-inaccessible | backend/tests/test_tenant_scoped_store.py |
| Documentation | Authorization model, roles, tenant IDs, audit, upload constraints, quotas, legacy-claim procedure, sandbox limitations, and rehearsal command | docs/PHASE_6_AUTHORIZATION_MODEL.md |

## CI acceptance criteria

The integrated main branch is considered code-verified only when the latest commit has all required CI jobs green:
- Frontend type-check, unit tests, and production build.
- Backend Ruff checks and complete test suite on Python 3.12.
- Backend Ruff checks and complete test suite on Python 3.13.

A successful run on an earlier commit does not verify a newer commit. Confirm the exact commit SHA and all jobs in GitHub Actions before calling the branch green.

## Release gates that code cannot honestly self-certify

These are not silently marked complete by unit tests or a successful CI run:

1. **Production identity-provider verification:** configure the real issuer, audience, and JWKS endpoint in the target environment; verify key rotation and unknown-key refresh behavior against that provider; verify provider-specific access-token semantics. Do not use mock tests as proof of live-provider behavior.
2. **Production migration rehearsal:** execute a reviewed rehearsal against a sanitized, representative database snapshot; verify backup and restore, WAL handling, downtime, rollback, record counts, and explicit ownership manifest. The automated rehearsal command is a preflight, not a substitute.
3. **Independent security review:** review authentication, role grants/revocation, tenant isolation, audit tamper-resistance/retention, quota race conditions, secrets management, dependency risks, and deployment configuration.
4. **OS-level sandbox review:** the worker process and POSIX resource limits are defense in depth only. The new adapter boundary prevents production fallback to that worker, but a real reviewed sandbox adapter is still required. A production multi-tenant service needs a separately reviewed isolation boundary for filesystem, network, syscalls, process capabilities, and kernel attack surface (for example, a hardened container or dedicated execution service with explicit policy). Windows does not receive the POSIX resource limits.
5. **Operational deployment checks:** secret management, TLS termination, least-privilege database/file permissions, audit storage monitoring, backup/restore, alerting, rate limits, and incident response must be verified in the real environment.

## Completion rule

Do not declare Phase 6 production-ready until the implementation checklist is covered by green CI and each release gate above has an owner, recorded evidence, and explicit sign-off. Any unverified gate remains open by definition. No pull request is merged by this checklist.
