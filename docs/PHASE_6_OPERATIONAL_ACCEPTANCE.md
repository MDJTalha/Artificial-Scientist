# Phase 6 — Operational Readiness and Final Acceptance

**Status: acceptance checklist defined; production readiness NOT VERIFIED.**
This checklist collects deployment controls, exact-commit CI evidence, independent review, and sign-off. A green unit-test run is necessary but does not prove a production deployment is safe.

## 1. Deployment control verification

### Identity and secrets
- [ ] Production OIDC provider, issuer, audience, JWKS endpoint, access-token semantics, and rotation evidence approved (see docs/PHASE_6_OIDC_PROVIDER_VALIDATION.md).
- [ ] Secrets stored in the approved secret manager; no credentials committed to source, container images, logs, tickets, or CI artifacts.
- [ ] Secret access restricted to required workloads/operators; rotation and revocation procedure tested.
- [ ] Production mode is explicit; development identity bypass and shared-key fallback cannot be enabled accidentally.

### Network and application
- [ ] TLS is enforced at the public boundary; certificate renewal and redirect behavior verified.
- [ ] Trusted proxy and forwarded-header behavior is configured explicitly; clients cannot spoof scheme/host identity used for security decisions.
- [ ] CORS, allowed origins, request body limits, upload limits, timeouts, and rate limits match approved deployment policy.
- [ ] Health/readiness checks do not expose secrets, configuration, tenant data, or internal exception details.
- [ ] Dependency lock/version evidence and vulnerability review are current for the exact deployed commit.

### Data and audit
- [ ] Database and attachment directories use least-privilege identities and permissions; attachment paths cannot escape their storage root.
- [ ] Database, backup, and attachment encryption/access controls are verified against policy.
- [ ] Audit retention, integrity/tamper detection, monitoring, and alert ownership are configured.
- [ ] Backups are scheduled, access-restricted, and restore-tested; database and attachment backup consistency is demonstrated.
- [ ] Tenant quotas, concurrency behavior, request denial auditing, and audit-persistence fail-closed behavior are verified.

### Execution boundary
- [ ] Untrusted/arbitrary code execution remains disabled unless a separately reviewed OS-level sandbox is deployed and tested.
- [ ] Worker timeouts/resource limits are treated as defense-in-depth, not as an OS sandbox.
- [ ] Filesystem, network, syscall, process, privilege, and kernel boundary tests are reviewed for the actual execution environment.

### Operations and response
- [ ] Metrics and alerts exist for authentication failures, JWKS failures, authorization denials, quota exhaustion, scanner outages, audit failures, worker timeouts, and unexpected process exits.
- [ ] On-call owner, incident severity criteria, escalation route, and response runbook are named and tested.
- [ ] Rate-limit, provider outage, database-full, disk-full, backup failure, scanner failure, and rollback scenarios are rehearsed.
- [ ] RTO/RPO, retention, recovery objectives, and data-loss reconciliation policy are approved by accountable owners.

## 2. Exact-commit CI evidence

Before a phase branch or PR is called verified, capture the exact head SHA and all required workflow results. Required repository CI jobs are:

- Frontend type-check, unit tests, and production build.
- Backend Ruff checks and complete tests on Python 3.12.
- Backend Ruff checks and complete tests on Python 3.13.

Do not reuse a green result from an earlier SHA. If a commit changes after CI, repeat verification on the new SHA. A missing workflow result is pending/unverified, not a pass. Review failed job logs and fix root causes before retrying.

Evidence record for each candidate PR:

| Field | Value to record |
|---|---|
| PR and title | Not yet recorded |
| Base and head branch | Not yet recorded |
| Exact head SHA | Not yet recorded |
| Required job results and links | Not yet recorded |
| Changed-file/security review | Not yet recorded |
| Reviewer and decision | Not yet recorded |
| Merge method and merge SHA | Not yet recorded |

## 3. Required review evidence

- [ ] Independent review of OIDC trust configuration and provider-specific rotation evidence.
- [ ] Independent review of tenant isolation, role grants/revocation, object-level authorization, audit behavior, and quota concurrency.
- [ ] Independent review of migration manifest, backup/restore, WAL handling, attachment consistency, rollback, and RTO/RPO.
- [ ] Independent review of the OS-level execution sandbox design and adversarial tests.
- [ ] Dependency/security review and production configuration review.
- [ ] All accepted exceptions have a named risk owner, expiry/review date, and compensating controls.

## 4. Dependency-ordered PR acceptance

Do not merge stacked PRs out of order. Verify the actual current base/head SHAs before each merge and re-check CI after the base branch changes.

1. Review and merge the Phase 6 core controlled-lab implementation PR only when its required CI is green and code review is accepted.
2. Rebase/refresh and validate the tenant identity, quotas, audit, legacy ownership, and cross-tenant security PR against the merged core branch. Merge only after exact-SHA CI and review pass.
3. Validate the sandbox release-gate and regression-test PRs in dependency order. These PRs do not themselves implement a full OS sandbox and cannot satisfy the sandbox release gate.
4. Validate the OIDC provider-evidence and migration/recovery runbook PRs. Documentation CI does not complete live provider verification or the real backup/restore drill.
5. Complete operational controls, independent review, and final acceptance evidence before any production-readiness declaration.
6. After each merge, record the merge SHA and rerun required CI on the resulting integration branch. If a later PR's base moves or conflicts, resolve and retest before proceeding.

## 5. Final acceptance decision

Phase 6 may be marked production-ready only when:

- All required code is integrated and exact-commit CI is green.
- Production identity provider and key rotation are verified with real evidence.
- Production-like migration, backup/restore, WAL/attachment recovery, and rollback rehearsal passes.
- Independent security review accepts the identity, tenant-isolation, audit, quota, and sandbox boundaries.
- Deployment controls, monitoring, incident response, and recovery objectives are verified in the target environment.
- Every release gate has a named owner, evidence link, date, and explicit approval.

Any missing evidence is an open gate. A document, mock test, unmerged PR, stale CI result, or undocumented verbal assurance does not satisfy the acceptance criterion.

## 6. Current status

- This document is an acceptance checklist, not evidence of deployed operational controls.
- Production provider verification, production-like migration/restore/rollback rehearsal, independent security review, OS-level sandbox review, and target-environment operational verification remain unverified until evidence is attached and approved.
- Final production acceptance: **BLOCKED / NOT VERIFIED**.