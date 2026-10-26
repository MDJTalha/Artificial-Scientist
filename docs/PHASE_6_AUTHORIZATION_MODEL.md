# Phase 6 — Identity, Authorization, and Tenant-Isolation Design

**Status: OIDC validation, tenant directory, tenant membership checks on lab routes, and tenant-scoped run/artifact persistence are implemented on the working branch. Tenant-wide binary and JSON artifact count/byte quotas and lab-run count quotas use serialized SQLite transactions. CI passed on commit `fe4d3ccf7cbb74632d05656ef60aba5b3e6619f4`; every subsequent code change must be re-verified. Complete adversarial coverage, production identity-provider verification, migration rehearsal, and independent security review remain outstanding.**  
**Scope:** controlled-lab runs, execution attempts, JSON artifacts, binary attachments, exports, and retention records.

## Security problem

The router now supports configured OIDC bearer validation and tenant membership authorization, while retaining the legacy `X-Lab-API-Key` path only when OIDC is not configured. A shared API key proves possession of one deployment secret; it does not establish an individual user, organization, role, or ownership relationship. Run IDs are UUIDs, but unguessable identifiers are not authorization. Although tenant-scoped controls are implemented, production exposure remains blocked on provider-specific verification, deployment hardening, independent security review, and the separate OS sandbox review.

## Decisions

1. **Do not infer identity from a shared secret.** The current API key remains a temporary deployment-level gate. It must not be used as a tenant ID, user ID, role, or audit actor.
2. **Authenticate at a documented trust boundary.** Prefer a maintained OIDC/OAuth2 identity provider or a separately reviewed service-to-service credential system. Validate issuer, audience, signature, expiry, and allowed algorithms; reject unsigned or ambiguous tokens. Do not write a custom password or JWT system as a shortcut.
3. **Use immutable internal identifiers.** Map an authenticated external subject to an internal principal ID. Tenant membership is a separate relation; do not trust a client-supplied tenant ID without checking membership and role.
4. **Authorize every object access.** Apply ownership/tenant filters in the persistence layer for runs, execution status, JSON artifacts, binary artifacts, exports, verification, and retention. A route-level check alone is not sufficient if a storage method can retrieve arbitrary IDs.
5. **Use deny-by-default roles.** Initial roles should be minimal: tenant administrator, researcher/editor, and read-only auditor/viewer. Define action permissions explicitly; do not grant permissions from unknown roles. Retention and system-wide operations are service/operator actions, not ordinary tenant permissions.
6. **Preserve existing records safely.** A schema migration must define how legacy records without tenant ownership are handled. Do not silently assign them to an arbitrary customer. Keep them inaccessible to tenant-scoped APIs until an explicit operator migration/claim process assigns ownership.
7. **Separate tenant quotas from global limits.** Retain per-run safety caps, then add transactionally enforced per-tenant run, artifact-count, and storage-byte budgets. A quota check must be atomic with persistence to avoid concurrent oversubscription.
8. **Audit security-relevant actions.** Record principal, tenant, action, target, outcome, timestamp, and correlation ID for access-denied events, exports, uploads/deletions, role changes, and operator retention actions. Never log bearer tokens, API keys, or raw scientific payloads by default.
9. **Fail closed.** Missing identity configuration outside development, invalid identity, missing tenant membership, ambiguous legacy ownership, or an unavailable authorization dependency must not permit data access.
10. **Keep local development explicit.** Development bypasses must be opt-in and local-only; production-like test environments must exercise authentication and authorization rather than relying on the development bypass.

## Required implementation sequence

- [x] Add provider-neutral OIDC bearer-token validation using maintained PyJWT/JWKS support; configure issuer, audience, and HTTPS JWKS URL explicitly. This validates identity claims but does not implement a provider-specific login flow.
- [ ] Select and document the production identity provider and verify its access-token format, key rotation, and deployment configuration.
- [x] Add SQLite persistence primitives for immutable principal IDs, tenants, explicit memberships, supported roles, and security audit events.
- [x] Add additive schema-migration and legacy-record ownership regression tests; legacy records remain unowned and are excluded from tenant-scoped run/artifact storage. A production migration rehearsal and review remain open.
- [x] Enforce configured OIDC bearer validation on the lab router; when any OIDC setting is configured, partial configuration fails closed and the legacy shared API key cannot bypass OIDC.
- [x] Propagate the validated identity into request context; add an explicit role/action matrix that denies unknown roles and actions.
- [x] Resolve validated request identity to a stable principal ID and require active tenant membership and action permission on run, execution-status, JSON artifact, binary artifact, verification, and export routes.
- [x] Add nullable tenant ownership columns to run and execution-attempt records; legacy rows remain unowned rather than being assigned arbitrarily.
- [x] Add an explicit dry-run-first, operator-authorized, conflict-rejecting legacy ownership claim tool with transactional audit records and regression tests; production rollout still requires an operator-run migration rehearsal and review.
- [x] Add tenant filters to run lists/reads, execution-status reads, JSON artifact lists/reads, binary artifact lists/reads, and export/verification route storage calls.
- [x] Add transactionally enforced per-tenant binary-attachment count and byte caps, with regression tests across multiple runs.
- [x] Add a tenant-wide lab-run count cap with a serialized reservation transaction and regression coverage. Only live run records and active execution reservations consume slots; failed/interrupted attempts and retention-purged runs release the live quota.
- [x] Add transactionally enforced per-tenant JSON artifact count and byte budgets with regression tests.
- [x] Add concurrency stress tests for binary uploads, run creation, and tenant-wide JSON artifact reservations; a purged or failed run no longer consumes a live run slot, and run-quota exhaustion is returned as HTTP 429. CI must pass on the latest commit before the branch is considered verified.
- [x] Keep stale execution recovery tenant-scoped: a persisted run is reconciled only when its ownership matches the execution attempt; mismatches are marked interrupted rather than cross-reconciled. Persist tenant-scoped lab request outcomes (allowed, denied, failed) with principal, tenant, action, object target, correlation ID, route, method, and HTTP status; all HTTP 4xx responses, including quota rejection, are classified as denied, and 5xx as failed. Correlation IDs from clients are restricted to a conservative 1–128 character ASCII alphabet; invalid values are replaced with server-generated UUIDs. Audit metadata excludes credentials and request payloads. Authentication failures occurring before tenant resolution are recorded as anonymous request events. Audit persistence failure blocks the response.
- [x] Add negative cross-tenant API tests for run reads, execution status, verification, exports, JSON artifact listing/read, binary artifact listing/download, and binary upload before scanning; execution-recovery reconciliation also checks tenant ownership. UUID substitution is exercised with another tenant's run and artifact identifiers. Binary upload rejects malformed or negative `Content-Length` values before scanning, compares oversized decimal lengths without converting attacker-controlled giant integers, rejects empty bodies before invoking the malware scanner, and validates the declared media type before reading or scanning the upload. The isolated execution helper also rejects zero, negative, NaN, and infinite worker deadlines before starting a process, with regression coverage. Invalid correlation IDs are replaced with server-generated UUIDs before audit persistence. Additional adversarial review remains required before production rollout.
- [x] Validate tenant selectors as canonical UUIDs before opening the tenant directory or persisting selector data. Malformed or oversized selectors are denied and audited as unscoped request events, preventing attacker-controlled tenant-header values from being stored in the audit database. Regression test covers a 100,000-character selector.
- [ ] Verify behavior in CI and conduct an independent security review before exposing untrusted or multi-tenant traffic.

## Legacy ownership claim procedure

The branch now includes `artificial_scientist.legacy_claim.claim_legacy_runs`, with a CLI entry point in `backend/src/artificial_scientist/legacy_claim.py`. It is intentionally separate from normal API traffic.

- Prepare a reviewed JSON manifest containing only explicit `run_id` and existing `tenant_id` UUID pairs.
- Run in dry-run mode first. The command refuses to initialize a missing database and verifies that every referenced run/attempt and tenant exists.
- Applying requires `--apply` and an existing internal `--operator-principal-id`. Conflicting ownership rejects the whole operation; it never overwrites a different tenant assignment.
- Run and execution-attempt ownership updates and the corresponding `legacy:claim` audit events are committed in one SQLite transaction. Re-running a matching claim is safe and records an audit event.
- Review the dry-run output and backup the database before applying. This is an operator tool, not a self-service tenant endpoint.

Example manifest:

```json
{
  "claims": [
    {
      "run_id": "00000000-0000-4000-8000-000000000001",
      "tenant_id": "00000000-0000-4000-8000-000000000002"
    }
  ]
}
```

Dry-run:

```powershell
python -m artificial_scientist.legacy_claim --database .\\data\\lab.sqlite3 --manifest .\\legacy-claims.json
```

Apply only after reviewing the dry-run and taking a backup:

```powershell
python -m artificial_scientist.legacy_claim --database .\\data\\lab.sqlite3 --manifest .\\legacy-claims.json --apply --operator-principal-id 00000000-0000-4000-8000-000000000003
```

The claim tool does not automatically assign owners to records without a manifest entry. Retention records for already-deleted runs are not claimable by this workflow and require a separate reviewed retention-evidence migration.

## Minimum acceptance tests

- Unauthenticated and malformed/expired/wrong-audience identities are denied outside development.
- A valid principal without tenant membership is denied.
- A principal from tenant A cannot list, read, verify, export, upload to, or download artifacts from tenant B, even when supplied a valid object UUID.
- Viewer/editor/admin permissions are tested as a matrix; unknown roles are denied.
- Legacy records without an explicit owner are not visible to tenant-scoped users.
- Concurrent requests cannot exceed configured tenant quotas.
- Audit records contain no credential material and cannot be supplied or overwritten by the client.

## Non-goals for the current shared-key implementation

This design does not claim that the existing API key provides user identity, RBAC, tenant isolation, per-user accountability, rate limiting, or SaaS readiness. No arbitrary generated code may be enabled based on this design alone. The OS sandbox and independent execution-boundary review remain separate requirements.

## Implemented OIDC configuration

Set all three environment variables to enable OIDC validation for the lab API:

- `ARTIFICIAL_SCIENTIST_OIDC_ISSUER`: exact expected issuer claim.
- `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE`: expected API audience.
- `ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL`: HTTPS JSON Web Key Set URL.

The validator accepts signed RS256 tokens only, validates issuer, audience, expiry and issued-at claims, and requires `sub`, `iss`, `aud`, `iat`, and `exp`. A missing or partial OIDC configuration fails closed outside development. Once any OIDC setting is supplied, the shared API key cannot be used as a fallback. The JWKS endpoint must use HTTPS.

This is an incremental authorization implementation, not a claim of production SaaS readiness. In production-like environments, each protected route requires a validated principal, an `X-Tenant-ID` selector, an active membership, and permission for the requested action. The tenant header selects a tenant but never grants access by itself. Run and artifact storage calls are tenant-scoped, and unknown or unowned object IDs return not-found responses. Development mode uses a fixed local-only principal and intentionally leaves storage unscoped for backwards-compatible local testing; do not expose development mode to untrusted traffic. Tenant quota enforcement, concurrent run/upload regression tests, request-outcome auditing, and the explicit legacy-claim tool passed CI on commit `fe4d3ccf7cbb74632d05656ef60aba5b3e6619f4`; the current CI run must pass after the tenant-selector validation changes before the branch is considered verified. Production rollout remains blocked on complete adversarial endpoint coverage, a reviewed migration rehearsal, provider-specific identity configuration and key-rotation verification, independent security review, and the separate OS-level execution sandbox review.

## Tenant-directory foundation added

The current branch adds `artificial_scientist.authorization.TenantDirectory`, which persists opaque principal IDs derived from the trusted issuer/subject pair, tenant records, explicit active memberships, and append-only-style security audit events. The supported roles are `tenant_admin`, `researcher`, `viewer`, and `auditor`; unknown roles/actions deny by default. Membership checks record allowed and denied outcomes without recording credentials or scientific payloads.

This is an incremental authorization and persistence layer, not a completed migration or enforcement layer. The current branch adds nullable tenant ownership to run and execution-attempt records and scopes protected run/artifact operations by tenant; legacy rows remain unowned and must stay inaccessible to tenant-scoped requests. Production migration rehearsal and review, complete cross-tenant endpoint coverage, production identity-provider verification, and independent security review remain open. Tenant-wide binary/JSON artifact and lab-run count quotas, concurrency regressions, request-outcome auditing, and legacy-claim regressions passed CI on commit `fe4d3ccf7cbb74632d05656ef60aba5b3e6619f4`; newer changes classify all client-error responses as denied, reject invalid scanner response encodings, reject malformed or oversized tenant selectors before audit persistence, and require canonical non-negative ASCII decimal `Content-Length` values for binary uploads. A negative-length regression test confirms rejection before malware scanning. CI must pass on the latest commit before verification is refreshed. Do not expose this branch to multiple customers until those controls and reviews are complete.
