# ASDS Deployment and Release Runbook

**Status:** Development/release-candidate runbook. The operator reported a healthy backend deployment on 2026-11-01; those endpoint responses establish application-process health only, not end-to-end readiness or production certification.

## Repository and deployment boundaries

- Repository: https://github.com/MDJTalha/Artificial-Scientist
- Current frontend implementation review: PR #40, branch `feat/complete-functional-workspaces` (open, draft, unmerged at the time this runbook was updated).
- Earlier backend endpoint: https://artificial-scientist.ethiodeploy.app
- API docs: https://artificial-scientist.ethiodeploy.app/docs
- Health: https://artificial-scientist.ethiodeploy.app/api/v1/health
- Application readiness: https://artificial-scientist.ethiodeploy.app/api/v1/ready
- Earlier Vercel preview: https://artificial-scientist-kq91e4vws.vercel.app (verify current deployment state before relying on it).

Do not infer that a deployment is current merely because its URL responds. Record the deployed commit SHA and deployment ID for every release candidate.

## Verified versus unverified evidence

The operator previously reported:
- `GET /`: service `Artificial Scientist`, version `0.1.0`, status `running`.
- `GET /api/v1/health`: status `ok`.
- `GET /api/v1/ready`: status `ready`, scope `application_only`.

The readiness scope is explicitly application-only. It does not prove database durability, identity-provider integration, research-provider connectivity, tenant isolation, audit persistence, scientific correctness, or operational resilience.

## Auth0 identity configuration

The frontend is an Auth0 Single Page Application (SPA). Use Authorization Code Flow with PKCE through the official Auth0 React SDK. Never place an Auth0 client secret in Vite variables or browser code.

Auth0 tenant domain currently configured in the frontend:
- Domain: `asds-artificial-scientist.us.auth0.com`
- Issuer: `https://asds-artificial-scientist.us.auth0.com/`
- JWKS: `https://asds-artificial-scientist.us.auth0.com/.well-known/jwks.json`

Before enabling API calls that require authentication, create/confirm an Auth0 API in the tenant. Its Identifier must be selected by the tenant owner and copied exactly; do not assume or invent it. Configure the same Identifier as the SPA's `VITE_AUTH0_AUDIENCE` and backend's `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE`.

Backend configuration for Auth0 JWT access tokens:

| Variable | Required value |
| --- | --- |
| `ARTIFICIAL_SCIENTIST_OIDC_ISSUER` | `https://asds-artificial-scientist.us.auth0.com/` |
| `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE` | Exact Identifier configured on the Auth0 API; not the SPA Client ID |
| `ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL` | `https://asds-artificial-scientist.us.auth0.com/.well-known/jwks.json` |
| `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE_CLAIM` | `aud` |
| `ARTIFICIAL_SCIENTIST_OIDC_TOKEN_USE` | Leave unset for Auth0; Cognito's `token_use` claim is not an Auth0 contract |
| `ARTIFICIAL_SCIENTIST_OIDC_REQUIRED_SCOPE` | Optional; set only to a scope actually defined on the Auth0 API and requested by the SPA |

The backend validator accepts RS256 JWTs and checks signature/JWKS, issuer, audience, expiry, issued-at, and subject. If a required scope is configured, it must be present in the token's space-delimited `scope` claim. The API must issue JWT access tokens for the configured Identifier. Do not send an ID token as an API bearer token.

The backend currently has generic OIDC settings that can validate Auth0 JWTs; this does not by itself prove that the deployed environment is configured or that a real token has passed end-to-end tests. Keep protected routes fail-closed until that test succeeds.

## Auth0 SPA settings

For local development:
- Allowed Callback URLs: `http://localhost:5173/`
- Allowed Logout URLs: `http://localhost:5173/`
- Allowed Web Origins: `http://localhost:5173`

Add each Vercel Preview and Production origin explicitly to the relevant Auth0 allowlists. Origins have no path or trailing slash. Callback and logout URLs include the exact path used by the application.

Vercel Preview environment variables:
- `VITE_AUTH0_DOMAIN=asds-artificial-scientist.us.auth0.com`
- `VITE_AUTH0_CLIENT_ID`: the public SPA Client ID already configured locally
- `VITE_AUTH0_AUDIENCE`: exact Auth0 API Identifier (only after API creation/confirmation)
- `VITE_API_BASE_URL=https://artificial-scientist.ethiodeploy.app` (only if this remains the verified backend URL)
- `VITE_ASDS_TENANT_ID`: only after the principal has been explicitly provisioned as a member of that tenant

Vite variables are embedded at build time. Redeploy the corresponding Vercel environment after changing them. Never configure a SPA client secret.

## Backend CORS

Set `ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS` to a comma-separated allowlist of exact origins actually used by the intended frontend deployment. Include local development only in a development environment. Do not use wildcard origins. Verify preflight and actual browser requests from the exact preview origin, and verify an unlisted origin is rejected.

## Persistence and authorization boundaries

- Current persistence modules use SQLite-specific SQL. A `DATABASE_URL` alone does not convert them to PostgreSQL.
- Do not store real tenant/research data on an unverified ephemeral SQLite filesystem.
- The general research-record/discovery production gate must remain enabled until tenant ownership, tenant-scoped persistence, authorization, migration and isolation tests are implemented and independently reviewed.
- Lab tenant authorization depends on a validated principal and an explicit server-side membership. A client-provided `X-Tenant-ID` is only a selector, never proof of membership.
- Audit persistence must remain fail-closed for protected lab operations.
- The computational runner is not an OS-level sandbox. Do not expose arbitrary generated code execution.
- Scientific hypotheses and automated assessments are drafts requiring independent evidence and human/domain-expert review; they are not proof of truth, causality, or novelty.

## Verification and release sequence

1. Record repository branch, commit SHA, PR, workflow run URL, and exact deployment IDs.
2. Confirm the current deployed backend and frontend commit SHAs before changing configuration.
3. Configure the Auth0 API Identifier and scopes, then request a real JWT access token for that audience.
4. Configure backend Auth0 issuer, audience, JWKS, and exact CORS origins. Keep the audience and scope values consistent with the Auth0 API configuration.
5. Test from the actual Vercel browser origin: CORS preflight, health, readiness, OpenAPI, and representative API calls.
6. Test protected routes with no token, malformed token, wrong issuer, wrong audience, expired token, wrong signature, missing scope, and a valid Auth0 access token. Expect fail-closed behavior for every invalid case.
7. Test tenant membership, cross-tenant read/write denial, role boundaries, membership revocation, and audit-store failure behavior.
8. Implement and verify durable PostgreSQL persistence, migrations, concurrency, transaction rollback, backup/restore, and tenant isolation before moving real data.
9. Verify all frontend workspaces at desktop/tablet/mobile widths, including loading, empty, success, error, offline, and unauthorized states.
10. Run backend Python 3.12/3.13 lint and tests plus frontend typecheck, unit tests, and production build on the exact PR head.
11. Complete independent security review, scientific benchmark/domain review, monitoring and operational acceptance before production release.

## Current known release blockers

- Auth0 API Identifier and required scopes have not yet been confirmed by the tenant owner.
- Real Auth0 access-token validation against the deployed backend has not yet been demonstrated.
- Production Vercel environment variables and CORS origin alignment have not yet been independently verified.
- PostgreSQL persistence and migration strategy are not implemented/verified.
- General research-record/discovery routes remain fail-closed outside development.
- OS-level computational sandboxing and independent scientific validation remain outstanding.
- No production certification or production-readiness claim is supported by the current evidence.

## Release evidence record

For each release candidate record:
- Git commit SHA, branch, PR and reviewer/approval state.
- CI workflow URL and all job outcomes.
- Backend deployment ID, deployed SHA, health/readiness output.
- Frontend deployment ID, deployed SHA, URL and environment.
- CORS browser preflight and API integration results.
- Auth0 issuer/audience/scope validation result (never record tokens).
- PostgreSQL migration, backup/restore, tenant-isolation, concurrency and audit results.
- Security review owner, scope, findings and remediation.
- Scientific benchmark/domain review and known limitations.
- Explicit release approval.

Never include secrets, access tokens, private connection strings, or private research data in this record.
