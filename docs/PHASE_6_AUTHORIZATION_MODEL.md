# Phase 6 — Identity, Authorization, and Tenant-Isolation Design

**Status: OIDC validation, tenant directory, tenant membership checks on lab routes, and tenant-scoped run/artifact persistence are implemented on the working branch; complete adversarial coverage, quotas, production identity-provider verification, and independent security review remain outstanding.**  
**Scope:** controlled-lab runs, execution attempts, JSON artifacts, binary attachments, exports, and retention records.

## Security problem

The lab router supports OIDC bearer-token validation when OIDC is configured, with a shared `X-Lab-API-Key` fallback only when no OIDC settings are supplied. That legacy key proves possession of one deployment secret; it does not establish a user, organization, role, or ownership relationship. Run IDs are UUIDs, but unguessable identifiers are not authorization. Tenant-scoped persistence is implemented for run and execution-attempt records and associated artifact lookups, but the design remains incomplete until adversarial route coverage, quotas, explicit local-development controls, and deployment evidence are in place.

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
- [x] Add nullable `tenant_id` columns to run and execution-attempt records via backward-compatible SQLite schema migration; legacy records remain unowned (`NULL`) and are excluded from tenant-scoped queries. Additional adversarial migration tests remain required.
- [x] Enforce configured OIDC bearer validation on the lab router; when any OIDC setting is configured, partial configuration fails closed and the legacy shared API key cannot bypass OIDC.
- [x] Propagate the validated identity into request context; add an explicit role/action matrix that denies unknown roles and actions.
- [x] Resolve validated request identity to a stable principal ID and require active tenant membership and action permission on run, execution-status, JSON artifact, binary artifact, verification, and export routes.
- [x] Add tenant ownership to run and execution-attempt records; legacy rows are not automatically assigned to any tenant. A reviewed operator-controlled claim/migration workflow is still not implemented.
- [x] Add tenant filters to run lists/reads, execution-status reads, JSON artifact lists/reads, binary artifact lists/reads, and export/verification route storage calls.
- [ ] Add transactional per-tenant quotas and tests for concurrent uploads and run creation.
- [x] Add the tenant-directory audit-event persistence primitive, bounded metadata validation, and allowed/denied membership audit events. Route-level correlation and complete audit coverage for exports, uploads, role changes, and retention are still outstanding.
- [ ] Expand negative cross-tenant tests across every object endpoint, including UUID substitution for export, verification, execution status, uploads, and downloads.
- [ ] Verify behavior in CI and conduct an independent security review before exposing untrusted or multi-tenant traffic.

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

This is an incremental authorization implementation, not a claim of production SaaS readiness. If `ARTIFICIAL_SCIENTIST_ENV` is unset, the application defaults to `production`; protected lab routes therefore require configured authentication and fail closed when it is missing. For local development only, explicitly set `ARTIFICIAL_SCIENTIST_ENV=development`. In production-like environments, each protected route requires a validated principal, an `X-Tenant-ID` selector, an active membership, and permission for the requested action. The tenant header selects a tenant but never grants access by itself. Run and artifact storage calls are tenant-scoped, and unknown or unowned object IDs return not-found responses. Development mode uses a fixed local-only principal and intentionally leaves storage unscoped for backwards-compatible local testing; do not expose development mode to untrusted traffic. Production rollout remains blocked on expanded negative tests, tenant quotas, provider-specific configuration review, and independent security review.

## Tenant-directory foundation added

The current branch adds `artificial_scientist.authorization.TenantDirectory`, which persists opaque principal IDs derived from the trusted issuer/subject pair, tenant records, explicit active memberships, and append-only-style security audit events. The supported roles are `tenant_admin`, `researcher`, `viewer`, and `auditor`; unknown roles/actions deny by default. Membership checks record allowed and denied outcomes without recording credentials or scientific payloads.

This is an incremental implementation, not a completed security boundary. The run and execution-attempt tables now carry nullable tenant ownership, and tenant-aware store methods scope run reads/lists, execution status, JSON artifacts, binary artifacts, and related run operations. Legacy rows remain unowned and are excluded from tenant-scoped queries; no automatic ownership is inferred. Do not expose this branch to multiple customers until endpoint-by-endpoint cross-tenant negative tests, quotas, explicit development-mode controls, production provider configuration, and independent security review are complete.
