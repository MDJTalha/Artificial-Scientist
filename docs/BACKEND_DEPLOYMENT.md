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

## Amazon Cognito identity provider

The repository includes `infra/aws/cognito-user-pool.yaml`. It provisions an Amazon Cognito User Pool, a public OAuth authorization-code client (no client secret), PKCE-compatible hosted UI domain, and the `asds-api/access` resource-server scope. Self-registration defaults to disabled; create users through a controlled administrator workflow until tenant onboarding and abuse controls are accepted. After an administrator role and Cognito service access are available, deploy it with `aws cloudformation deploy --template-file infra/aws/cognito-user-pool.yaml --stack-name asds-identity --region <region> --parameter-overrides DomainPrefix=<unique-prefix> CallbackUrls=https://<frontend-domain>/auth/callback LogoutUrls=https://<frontend-domain>/ EnableSelfRegistration=false`. Inspect the change set and outputs before configuring either application.

Configure the API with the CloudFormation outputs:

- `ARTIFICIAL_SCIENTIST_OIDC_ISSUER`: `https://cognito-idp.<region>.amazonaws.com/<user-pool-id>`
- `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE`: User Pool app client ID
- `ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL`: `<issuer>/.well-known/jwks.json`
- `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE_CLAIM=client_id`
- `ARTIFICIAL_SCIENTIST_OIDC_TOKEN_USE=access`
- `ARTIFICIAL_SCIENTIST_OIDC_REQUIRED_SCOPE=asds-api/access`

The browser uses the Cognito hosted UI authorization-code flow with PKCE and sends the short-lived access token as a bearer token. Configure `VITE_COGNITO_DOMAIN`, `VITE_COGNITO_CLIENT_ID`, `VITE_COGNITO_REDIRECT_URI`, `VITE_COGNITO_LOGOUT_URI`, and `VITE_COGNITO_SCOPES` in the frontend hosting environment. Callback and logout URLs must exactly match the Cognito app-client allowlists and use HTTPS in hosted environments. The web client has no embedded secret.

### Tenant onboarding

Authentication is not tenant membership. Research-record, knowledge-write, and lab APIs continue to require an active server-side tenant membership. After verifying the Cognito user `sub` in the User Pool, run the trusted operator command against the same persistent authorization database used by the API:

\`\`\`bash
PYTHONPATH=backend/src python backend/scripts/bootstrap_tenant_membership.py \\
  --database /app/data/asds.sqlite3 \\
  --issuer https://cognito-idp.<region>.amazonaws.com/<user-pool-id> \\
  --subject <verified-cognito-sub> \\
  --tenant-key <operator-controlled-tenant-key> \\
  --tenant-name "ASDS Research"
\`\`\`

Set the resulting tenant ID as `VITE_ASDS_TENANT_ID` in the frontend deployment. Never accept a tenant ID as proof of membership; the API checks membership and role against its own directory. The current SQLite-backed directory means this bootstrap procedure is only suitable for controlled staging until the persistence migration is complete.

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
