# Phase 6 — Identity, Authorization, and Tenant-Isolation Design

**Status: design decision; implementation and security verification are still required.**  
**Scope:** controlled-lab runs, execution attempts, JSON artifacts, binary attachments, exports, and retention records.

## Security problem

The current lab router uses a single shared `X-Lab-API-Key` outside development. That gate proves possession of one deployment secret; it does not establish a user, organization, role, or ownership relationship. Run IDs are UUIDs, but unguessable identifiers are not authorization. Until tenant ownership is implemented, the lab must be treated as a trusted single-deployment service and must not be exposed as a multi-customer SaaS API.

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

- [ ] Choose and document the supported identity-provider integration and token-validation library before coding authentication.
- [ ] Add principal, tenant, membership, and role-permission data models with schema migration tests.
- [ ] Add a request-scoped authenticated principal dependency and deny-by-default permission checks.
- [ ] Add tenant ownership to run and execution-attempt records; define a reviewed legacy-data migration.
- [ ] Enforce tenant scoping inside all run, artifact, export, verification, and status store operations.
- [ ] Add transactional per-tenant quotas and tests for concurrent uploads and run creation.
- [ ] Add security audit events without recording secrets or raw request payloads.
- [ ] Add negative cross-tenant tests for every object endpoint, including UUID substitution, export, verification, status, and binary downloads.
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
