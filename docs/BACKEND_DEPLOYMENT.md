# ASDS backend deployment

## Deployment status

The FastAPI backend is containerized, but **no remote backend has been deployed**. The Docker image and Compose profile provide a reproducible local runtime and a CI smoke-test target. They do not constitute a production deployment.

The production deployment is deliberately blocked until the following gates are closed:

1. **Identity and authorization:** configure a real OIDC issuer, audience, and JWKS endpoint; validate authentication on every non-public API route; implement the frontend authorization-code-with-PKCE login flow and bearer-token handling. The current backend has route-level protections for selected records, discovery, knowledge, and lab operations, but literature and mathematics routes are not protected by a global authentication layer. Do not expose the API to the public internet in this state.
2. **Tenant and data isolation:** verify tenant-scoped access for every persisted resource and review cross-tenant negative tests. Existing production fail-closed guards are intentional and must not be bypassed.
3. **Durable database:** the current persistence implementation is SQLite. The default database path is local to the container filesystem. A production service needs a supported durable database architecture, migration and rollback plan, backup/restore rehearsal, and concurrency validation. Do not put a multi-replica SQLite database on a shared network filesystem.
4. **Deployment identity:** use a dedicated least-privilege deployment role with GitHub Actions OIDC federation. Do not use AWS root credentials or long-lived root access keys for deployment.
5. **Operational controls:** configure TLS, exact CORS origins, secret management, logs/metrics/alerts, resource limits, vulnerability scanning, and an independently reviewed recovery procedure.

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

## AWS deployment target

The intended container target is ECS on Fargate behind an HTTPS Application Load Balancer, with ECR for image storage, CloudWatch for logs/metrics, Secrets Manager for runtime secrets, and a managed relational database after the persistence layer has been migrated and tested.

No ECS cluster or ECR repository was found in the connected AWS account. ECS and EC2 API calls currently return account subscription/opt-in errors in the regions probed. The account connection also identifies itself as the AWS root principal. For those reasons, no AWS resources were created and no public endpoint was opened. Enable the required AWS services in the chosen region and establish a dedicated deployment role before proceeding.

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
