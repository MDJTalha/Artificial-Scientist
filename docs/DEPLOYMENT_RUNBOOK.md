# ASDS Deployment and Release Runbook

**Status:** Live backend deployment verified by operator-provided endpoint responses on 2026-11-01. This runbook separates verified facts from configuration and release gates that still require testing.

## Deployed services

- Backend API: https://artificial-scientist.ethiodeploy.app
- Backend API documentation: https://artificial-scientist.ethiodeploy.app/docs
- Health: https://artificial-scientist.ethiodeploy.app/api/v1/health
- Application readiness: https://artificial-scientist.ethiodeploy.app/api/v1/ready
- Frontend preview (not a production release): https://artificial-scientist-kq91e4vws.vercel.app
- Working branch: `feat/complete-scientific-frontend`
- Review boundary: PR #39 remains open, draft, and unmerged until the repository checks and human review are complete.

## Verified deployment evidence

The operator reported these responses from the deployed service:

- `GET /`: service `Artificial Scientist`, version `0.1.0`, status `running`.
- `GET /api/v1/health`: status `ok`.
- `GET /api/v1/ready`: status `ready`, scope `application_only`.

The readiness endpoint intentionally does not claim that a database, identity provider, research provider, or other external dependency is available. A successful process/health check is not a production-readiness certification.

## Required backend environment configuration

Configure these values in the backend hosting provider's environment-variable settings. Do not commit credentials or secret values.

| Variable | Required configuration |
| --- | --- |
| `ARTIFICIAL_SCIENTIST_ENV` | `production` |
| `ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS` | Exact HTTPS origins of the intended Vercel frontend deployment(s), comma-separated. Do not use `*`. |
| `ARTIFICIAL_SCIENTIST_DB_PATH` | Current SQLite file path only for the existing deployment; SQLite on ephemeral hosting storage is not an approved production persistence strategy. |
| `ARTIFICIAL_SCIENTIST_OIDC_ISSUER` | Cognito user-pool issuer URL after the pool is provisioned and verified. |
| `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE` | Cognito app-client identifier expected by the backend validator. |
| `ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL` | HTTPS JWKS URL belonging to the configured issuer. |
| `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE_CLAIM` | `client_id` for Cognito access tokens, matching the actual token contract. |
| `ARTIFICIAL_SCIENTIST_OIDC_TOKEN_USE` | `access` |
| `ARTIFICIAL_SCIENTIST_OIDC_REQUIRED_SCOPE` | `asds-api/access`, if that scope is provisioned on the Cognito resource server. |

The current backend CORS default is localhost-only. The frontend preview origin must be explicitly added to `ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS` before browser integration can be considered verified. Add the final production frontend origin separately when one exists. Keep the allowlist narrow and exact.

Do not enable Cognito configuration with placeholder values. Provision the user pool, app client, resource-server scope, callback URLs, and logout URLs first; then validate a real access token end-to-end. Do not use an ID token as an API access token.

## Required Vercel environment configuration

For the preview environment, set:

- `VITE_API_BASE_URL=https://artificial-scientist.ethiodeploy.app`

Set the `VITE_COGNITO_*` values only after the matching Cognito app client and HTTPS callback/logout URLs are provisioned. The Vercel frontend uses OAuth authorization-code flow with PKCE and a public client; do not add a client secret to frontend variables.

Set `VITE_ASDS_TENANT_ID` only after a tenant and membership have been explicitly provisioned for the authenticated principal. A client-supplied tenant ID is not authorization.

Vite variables are embedded at build time. Redeploy the relevant Vercel environment after changing them.

## Safe verification sequence

1. Confirm the deployed backend commit and provider environment before changing deployment settings.
2. Configure the exact Vercel preview origin in backend CORS. Redeploy the backend only after reviewing the environment change.
3. Configure `VITE_API_BASE_URL` in Vercel Preview and redeploy the frontend.
4. From the actual Vercel preview browser origin, verify preflight and GET requests to `/api/v1/health`, `/api/v1/ready`, and `/openapi.json`. Verify an unlisted origin is not granted CORS access.
5. Exercise representative mathematics and literature routes with valid, invalid, and oversized requests. Confirm documented response codes and bounded behavior.
6. Verify all protected routes fail closed when OIDC is absent or invalid. Then test a real Cognito access token, issuer, audience, expiry, token-use, scope, and tenant membership.
7. Verify lab authorization and audit persistence, including cross-tenant read/write denial and audit-store failure behavior.
8. Verify persistent database storage, backup, restore, migrations, rollback, concurrency, and tenant isolation against a real PostgreSQL test database before migrating any data.
9. Run the full backend Python 3.12/3.13 and frontend typecheck/test/build CI on the exact PR head.
10. Complete independent security and scientific-domain review before production release.

## Known release blockers and safety gates

- **PostgreSQL:** current stores use SQLite-specific SQL and persistence behavior. Setting a `DATABASE_URL` alone does not migrate them. Implement and test a persistence abstraction and migration plan before using PostgreSQL.
- **Persistence durability:** do not store real tenant/research data on an unverified ephemeral SQLite volume.
- **Identity:** Cognito deployment and real provider-token verification remain external gates until proven with live configuration.
- **Tenant-scoped research records:** the production fail-closed gate for general records/discovery must remain enabled until record ownership and authorization are implemented and reviewed.
- **Computational isolation:** the bounded runner is not an OS-level sandbox. Do not expose arbitrary generated code execution.
- **Audit integrity:** preserve fail-closed behavior when audit persistence is unavailable.
- **Scientific validity:** generated hypotheses and automated assessments require human review and independent evidence; they are not proof of truth, causality, or novelty.
- **Release governance:** do not merge PR #39, switch the production branch, or represent the system as certified/production-ready without explicit approval and evidence for all required gates.

## Release evidence record

For every release candidate, record:

- Git commit SHA and branch.
- CI workflow run URL and Python/frontend job results.
- Backend deployment ID, deployed commit, health/readiness output.
- Frontend deployment URL, deployment ID, and environment.
- CORS browser preflight result and API integration test results.
- OIDC issuer/audience/scope verification (never record tokens).
- PostgreSQL migration, backup/restore, tenant-isolation, and audit test results.
- Security review owner, scope, findings, and remediation status.
- Known limitations and explicit release approval.

Never include secrets, access tokens, private connection strings, or personal research data in this record.
