# Release Evidence Matrix — 2026-11-01

This register separates **repository verification evidence** from **external release certification**. A green CI job is never treated as proof of an external gate.

| Gate / work item | Repository evidence | Verification command / protocol | Status |
|---|---|---|---|
| Endpoint-by-endpoint authorization matrix | `tests/test_release_authorization_matrix.py`, existing Phase 7 tenant isolation/release-gate suites | `pytest -q tests/test_release_authorization_matrix.py tests/test_phase7_tenant_isolation.py tests/test_phase7_release_gate.py` | Verified — CI run **1242** (workflow run **41225031000**), tested code commit **20681adc2520464a6735628bd0ddf78a3cfa9f61** |
| Cross-tenant adversarial coverage | Phase 7 isolation tests cover record reads/listing, discovery evidence and concurrent tenant writes; Phase 6 suites cover run/artifact/verification/export/upload negative paths | Full backend suite plus targeted release-gate suite | Repository complete after CI |
| Quota/ownership race testing | `tests/test_lab_quota_races.py` exercises atomic tenant run reservation and same-run ownership collision | `pytest -q tests/test_lab_quota_races.py` under Python 3.12/3.13 | Repository complete after CI |
| Migration/recovery fixtures | `tests/test_migration_recovery_assertions.py` verifies source byte identity, reopenability and no partial claim after failed rehearsal; existing rehearsal/migration suites remain required | `pytest -q tests/test_migration_recovery_assertions.py tests/test_phase6_rehearsal.py tests/test_phase7_tenant_migration.py` | Repository complete after CI |
| Frontend accessibility/E2E | Playwright + axe harness in `frontend/e2e/accessibility.spec.ts`; keyboard navigation, explicit gated posture and WCAG automated scan | `npm run typecheck && npm test && npm run build && npx playwright test` | Repository complete after CI |
| Release-gate policy validation | `docs/release/release-gates.json` + `scripts/validate_release_evidence.py` | `python scripts/validate_release_evidence.py` | Repository complete |
| Documentation reconciliation | This matrix plus `docs/CURRENT_STATUS.md` and release README distinguish repository evidence from external certification | Review against CI run and current tested code commit | Repository complete |
| Reviewed OS-level sandbox deployment | Repository only has fail-closed adapter boundary; no OS sandbox deployment evidence is present | Target-runtime deployment + adversarial filesystem/network/syscall/resource/cleanup protocol | **External gate open** |
| Live OIDC/JWKS provider validation | Mocked/unit identity tests are repository evidence only | Actual provider, claims, TLS/JWKS rotation/unknown-key refresh protocol | **External gate open** |
| Production migration/backup/restore rehearsal | Rehearsal implementation is tested against temporary SQLite snapshots | Sanitized representative production snapshot, backup/restore/WAL/migration/rollback and ownership reconciliation | **External gate open** |
| Independent security review | Internal tests are not independent review | Qualified reviewer sign-off covering auth, tenancy, audit, secrets, dependencies and deployment | **External gate open** |
| Operational deployment validation | No deployment environment is certified by CI | TLS, secrets, least privilege, monitoring, alerting, rate limits, incident response, scheduler and backup/restore | **External gate open** |
| Scientific replication and domain validation | Scientific tools and evidence structures are implemented and tested | Independent benchmark, replication, domain-expert review and scientific-integrity evaluation | **External gate open** |

## Final repository verification record

- Branch: `phase-release-verification-hardening`
- Implementation commit: `20681adc2520464a6735628bd0ddf78a3cfa9f61`
- Previously verified branch head: `f3a8661bcf9f2d5c6117e2193d4852896c471c36`
- GitHub Actions workflow: **Continuous Integration**, run **1242** / ID **41225031000**
- Backend: Python 3.12 and 3.13 full test suites + Ruff passed.
- Frontend: TypeScript type-check, unit tests, production build, Playwright/axe accessibility and conference-workspace E2E passed.
- Release-gate job: policy validation, Phase 6 hardening regressions, Phase 7 authorization/tenant regressions, and Phases 8–14 regressions passed.
- The previously verified CI run exercised the repository-side hardening baseline. The current branch additionally contains the production-validation runbook, configuration preflight, SQLite backup/restore helper, sanitized OIDC/JWKS probe, deterministic scientific smoke benchmark, independent security-review scope, scientific-validation protocol, and operations acceptance checklist. A new CI run is required before those additions are recorded as CI-verified.

## Additional integration-branch evidence

| Gate / work item | Repository evidence | Verification protocol | Status |
|---|---|---|---|
| Browser OIDC Authorization Code + PKCE | `frontend/src/lib/oidc.ts`, OIDC configuration/cryptographic tests, `App.tsx` session flow and `/api/v1/auth/session` backend route | Frontend unit/E2E; actual provider discovery, callback, token CORS, audience and JWKS rotation tests on the chosen provider | Repository implementation added; **live provider gate open** |
| Server-side tenant discovery and operator provisioning | `api/routes/auth.py`, `authorization.py`, `backend/scripts/provision_tenant.py`, session API tests | Provision multiple tenants/roles, authenticate, revoke membership and test cross-tenant denials | Repository implementation added; **operator provisioning and live membership evidence open** |
| Production readiness checks | `api/routes/health.py`, `tests/test_readiness.py` | Production-mode SQLite quick_check/write probe, OIDC configuration and HTTPS CORS negative/positive tests | Repository tests added; **target-host readiness open** |
| API container packaging | `deploy/api.Dockerfile`, `deploy/api.compose.yml`, API image/readiness CI job | Build image, run as non-root with read-only root, named persistent volume and readiness endpoint | CI image build/runtime smoke test pending on exact latest head; **host deployment open** |
| Single-node API deployment guide | `docs/deployment/API_CONTAINER_DEPLOYMENT.md` | Configure a real host, TLS reverse proxy, persistent volume, secrets, monitoring and restore | Documentation/template only; **external operations gate open** |
| Browser session and tenant authorization | In-memory token API client; server-side membership/action validation | Test every protected endpoint with each role and tenant, including invalid/revoked tokens and attempts to override tenant headers | Existing unit/regression coverage plus new tests; **full live browser role acceptance pending** |

### Current candidate and CI freshness

- Feature branch: `feat/research-workspace-v1`
- Draft integration PR: [#38](https://github.com/MDJTalha/Artificial-Scientist/pull/38), based on `phase-release-verification-hardening`; it remains unmerged.
- Run **1432** / workflow ID **41268749966** tested code commit `3e3e1e973a29f7a44e8d8b07585aaa2e0f66937e`; the frontend passed while Python 3.12/3.13 tests were still running at the time of the status record.
- Subsequent changes to the preflight validator and architecture/current-status documentation require a new passing run on the final branch head before this integration update is considered repository-verified.
- The previously successful run **1395** on `05f9634` validates the earlier UI/release-hardening scope only; it does not certify the subsequently added OIDC/readiness/container code.

## Evidence rules

For every external gate, the final release package must retain:

1. target environment and exact software/configuration version;
2. test protocol and commands;
3. timestamped outcome;
4. observed failures and limitations;
5. residual risks and mitigations;
6. independent/operator sign-off where required.

**Do not mark an external gate complete from repository tests, mocked services, screenshots, documentation, or CI alone.**
