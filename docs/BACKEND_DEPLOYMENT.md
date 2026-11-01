# ASDS backend deployment

## Deployment status

The FastAPI backend is containerized, but **no remote backend has been deployed**. The Docker image and Compose profile provide a reproducible local runtime and a CI smoke-test target. They do not constitute a production deployment.

The production deployment is deliberately blocked until the following gates are closed:

1. **Identity and authorization:** configure and verify a real OIDC issuer, exact API audience, and JWKS endpoint; validate authentication on every non-public `/api/v1` route; verify the frontend authorization-code-with-PKCE login flow and bearer-token handling against the deployed API. The backend now applies a global OIDC authentication middleware to non-public versioned API routes, while lab and records routers perform their own token validation and tenant-membership checks. Authentication alone is not tenant authorization: tenant-scoped authorization and negative cross-tenant tests must cover every persisted resource before public exposure.
2. **Tenant and data isolation:** verify tenant-scoped access for every persisted resource and review cross-tenant negative tests. Existing production fail-closed guards are intentional and must not be bypassed.
3. **Durable database:** the current persistence implementation is SQLite. The default database path is local to the container filesystem. A production service needs a supported durable database architecture, migration and rollback plan, backup/restore rehearsal, and concurrency validation. Do not put a multi-replica SQLite database on a shared network filesystem.
4. **Deployment identity:** use a dedicated least-privilege deployment role with GitHub Actions OIDC federation. Do not use AWS root credentials or long-lived root access keys for deployment.
5. **Operational controls:** configure TLS, exact CORS origins, secret management, logs/metrics/alerts, resource limits, vulnerability scanning, and an independently reviewed recovery procedure. The repository's current container/CI checks are not evidence of a live deployment; production acceptance requires a verified deployed commit, real Auth0 positive/negative tests, and database recovery evidence.

## Local container

From the repository root:

```bash
docker compose -f backend/compose.yaml up --build
```

The API is bound to loopback only:

- Health: http://127.0.0.1:8000/api/v1/health
- Readiness: http://127.0.0.1:8000/api/v1/ready
- OpenAPI: http://127.0.0.1:8000/openapi.json

The named Docker volume `asds-backend-data` retains local SQLite data across container replacement. The Compose profile intentionally sets the environment to development and binds the published port to 127.0.0.1. It is for local development and smoke testing only; do not copy its development setting to a public deployment.

## Runtime configuration

| Variable | Purpose |
|---|---|
| `ARTIFICIAL_SCIENTIST_ENV` | Runtime mode. Use production only after all production gates are met. |
| `ARTIFICIAL_SCIENTIST_DB_PATH` | SQLite path for the current implementation. |
| `ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS` | Comma-separated exact browser origins. No wildcard. |
| `ARTIFICIAL_SCIENTIST_OIDC_ISSUER` | Expected OIDC issuer URL. |
| `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE` | Expected API audience. |
| `ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL` | Trusted JWKS endpoint. |
| `OPENALEX_API_KEY` | Optional OpenAlex provider credential. |
| `CROSSREF_CONTACT_EMAIL` | Contact email for polite Crossref access. |

Never commit real secrets or put credentials in the image. Inject them from a managed secret store at runtime.

## Auth0 identity provider

The current frontend integration uses Auth0 Authorization Code Flow with PKCE through the Auth0 React SDK. The Cognito CloudFormation template and Cognito instructions below are legacy artifacts; they are not the active identity-provider configuration for this application.

Known Auth0 tenant configuration:
- Domain: `asds-artificial-scientist.us.auth0.com`
- Issuer: `https://asds-artificial-scientist.us.auth0.com/`
- JWKS: `https://asds-artificial-scientist.us.auth0.com/.well-known/jwks.json`
- SPA Client ID: public client identifier configured in the frontend; never treat it as an API audience or secret.

Before enabling protected API calls, the tenant owner must create or confirm an Auth0 API and its exact Identifier. The Identifier is not established by this repository and must not be guessed. Configure that exact value in both `VITE_AUTH0_AUDIENCE` and `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE`. Define scopes in the Auth0 API only when required by the deployed authorization policy; do not invent a scope name.

Backend configuration:
- `ARTIFICIAL_SCIENTIST_OIDC_ISSUER=https://asds-artificial-scientist.us.auth0.com/`
- `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE=<exact-auth0-api-identifier>`
- `ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL=https://asds-artificial-scientist.us.auth0.com/.well-known/jwks.json`
- `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE_CLAIM=aud`
- Leave `ARTIFICIAL_SCIENTIST_OIDC_TOKEN_USE` unset for Auth0 unless a provider-specific contract is deliberately implemented and tested.
- Configure `ARTIFICIAL_SCIENTIST_OIDC_REQUIRED_SCOPE` only when the matching scope is actually defined on the Auth0 API and requested by the SPA.

Frontend configuration:
- `VITE_AUTH0_DOMAIN=asds-artificial-scientist.us.auth0.com`
- `VITE_AUTH0_CLIENT_ID=<public-spa-client-id>`
- `VITE_AUTH0_AUDIENCE=<exact-auth0-api-identifier>`
- `VITE_API_BASE_URL=<verified-backend-origin>`
- `VITE_ASDS_TENANT_ID=<operator-provisioned-tenant-id>` only after membership is explicitly provisioned.

For local development, configure the exact callback and logout URL `http://localhost:5173/` and web origin `http://localhost:5173` in Auth0. Hosted preview/production callback, logout, and web-origin allowlists must be configured with the exact deployed frontend origins and paths. Never put a client secret in Vite variables.

Authentication is not tenant membership. The API must validate the access-token signature, issuer, audience, expiry, and required scope (if configured), then check active server-side tenant membership and role. A client-supplied tenant ID is only a selector. The tenant directory is currently SQLite-backed; controlled operator provisioning is not a substitute for the outstanding durable-database migration and production recovery rehearsal.

The Auth0 settings above describe the repository's intended provider contract, not proof that the deployed Auth0 tenant/API and backend environment are configured. Production acceptance requires a real access token and negative/positive end-to-end tests against the deployed API. Keep all protected routes fail-closed until those tests pass.

## AWS deployment target

The intended container target is ECS on Fargate behind an HTTPS Application Load Balancer, with ECR for image storage, CloudWatch for logs/metrics, Secrets Manager for runtime secrets, and a managed relational database after the persistence layer has been migrated and tested. Cognito provisioning is also currently blocked by the AWS account's `SubscriptionRequiredException` response.

No ECS cluster or ECR repository was found in the connected AWS account. ECS and EC2 API calls currently return account subscription/opt-in errors in the regions probed. The account connection also identifies itself as the AWS root principal. For those reasons, no AWS resources were created and no public endpoint was opened. Enable the required AWS services in the chosen region and establish a dedicated deployment role before proceeding.

## GitHub OIDC deployment automation

The repository includes `infra/aws/github-actions-deploy-role.yaml` and `.github/workflows/deploy-backend-ecs.yml`. An AWS administrator must apply the role template using an existing GitHub Actions OIDC provider, a pre-created ECR repository, ECS cluster/service, and the exact task execution/application role ARNs. The trust policy is restricted to `MDJTalha/Artificial-Scientist` on the configured deployment branch (default `main`). The role can push to one ECR repository, register task-definition revisions, update one ECS service, and pass only the two configured ECS task roles.

Configure these GitHub **repository or production-environment variables** before using the manual workflow: `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `ECR_REPOSITORY`, `ECS_CLUSTER`, `ECS_SERVICE`, `ECS_TASK_DEFINITION_FAMILY`, and `ECS_CONTAINER_NAME`. Protect the GitHub `production` environment with required reviewers. The workflow only runs from `main` via manual dispatch, builds an immutable image tagged with the commit SHA, registers a new task-definition revision, updates the ECS service, and waits for service stability. It does not create the VPC, load balancer, ECS service, database, secrets, or Cognito pool.

## Release verification

A backend deployment is not accepted until all of these have evidence:

- Backend unit and integration tests pass on the exact release commit.
- Container builds reproducibly and its health check passes.
- OIDC positive and negative tests pass against the real provider.
- Every public API route is inventoried and authenticated or explicitly allowlisted.
- Tenant isolation tests pass for all persisted data.
- Database migrations, backup, restore, and rollback are rehearsed.
- TLS, CORS, secrets, logs, metrics, alerts, and resource limits are verified.
- A production smoke test confirms the deployed version and API contract.
- Independent security and scientific-domain reviews are recorded.

Passing container build or health checks does not certify scientific validity, production security, or operational readiness.
