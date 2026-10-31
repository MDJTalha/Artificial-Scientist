# Release Evidence Matrix — 2026-10-31

This register separates **repository verification evidence** from **external release certification**. A green CI job is never treated as proof of an external gate.

| Gate / work item | Repository evidence | Verification command / protocol | Status |
|---|---|---|---|
| Endpoint-by-endpoint authorization matrix | `tests/test_release_authorization_matrix.py`, existing Phase 7 tenant isolation/release-gate suites | `pytest -q tests/test_release_authorization_matrix.py tests/test_phase7_tenant_isolation.py tests/test_phase7_release_gate.py` | Verified — CI run **1231** (workflow run **41224168508**), tested code commit **20681adc2520464a6735628bd0ddf78a3cfa9f61** |
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
- Tested code commit: `8c4eec72ba0e710c606b50956af0de4288015148`
- GitHub Actions workflow: **Continuous Integration**, run **1231** / ID **41224168508**
- Backend: Python 3.12 and 3.13 full test suites + Ruff passed.
- Frontend: TypeScript type-check, unit tests, production build, Playwright/axe accessibility and conference-workspace E2E passed.
- Release-gate job: policy validation, Phase 6 hardening regressions, Phase 7 authorization/tenant regressions, and Phases 8–14 regressions passed.
- This evidence-matrix synchronization is documentation-only and does not alter the tested implementation commit above.

## Evidence rules

For every external gate, the final release package must retain:

1. target environment and exact software/configuration version;
2. test protocol and commands;
3. timestamped outcome;
4. observed failures and limitations;
5. residual risks and mitigations;
6. independent/operator sign-off where required.

**Do not mark an external gate complete from repository tests, mocked services, screenshots, documentation, or CI alone.**
