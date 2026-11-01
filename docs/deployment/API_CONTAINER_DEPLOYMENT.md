# Single-node ASDS API Container Deployment

## Scope

This deployment package supplies a non-root FastAPI container and a single-node Docker Compose topology with a named SQLite data volume. It is an implementation/deployment template, not evidence that a public backend host, DNS, TLS reverse proxy, identity provider, backups, monitoring or recovery service has been configured.

The Compose service binds the API to 127.0.0.1 on the host. Put a separately managed reverse proxy or load balancer in front of it, terminate HTTPS there, and forward only the intended API host/path. Do not expose the container port directly to the public internet.

## Prerequisites

- Linux container host with Docker Engine and Compose plugin.
- A durable host volume for the named asds-api-data Docker volume, protected by the host's storage and backup policy.
- A TLS reverse proxy with a tested certificate chain and renewal process.
- A real OIDC provider configured as a public SPA client with Authorization Code + PKCE S256.
- An API access-token audience, HTTPS issuer and JWKS URI; access tokens must be RS256 JWTs accepted by the backend.
- A secret manager or protected operator environment to inject runtime settings. Do not commit a deployment .env file.

## Build and start

Run from the repository root. Export the OIDC and CORS values from the host's secret/configuration manager; the Compose template refuses to start if required values are missing.

    export ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS=https://research.example.test
    export ARTIFICIAL_SCIENTIST_OIDC_ISSUER=https://identity.example.test/
    export ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE=asds-api
    export ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL=https://identity.example.test/.well-known/jwks.json
    docker compose -f deploy/api.compose.yml config
    docker compose -f deploy/api.compose.yml build
    docker compose -f deploy/api.compose.yml up -d

Inspect the container and the application readiness endpoint:

    docker compose -f deploy/api.compose.yml ps
    curl --fail http://127.0.0.1:8000/api/v1/health
    curl --fail http://127.0.0.1:8000/api/v1/ready

The ready endpoint checks production database writability/integrity, OIDC configuration shape and HTTPS CORS origins. It does not contact the OIDC provider, test JWKS rotation, verify the external TLS proxy, inspect volume durability, or certify backups.

## Security posture in this template

- Non-root UID/GID 10001.
- Read-only container root filesystem.
- Dropped Linux capabilities and no-new-privileges.
- Bounded CPU, memory, process count and temporary filesystem in Compose.
- Persistent data mounted only at /var/lib/asds.
- API bound to host loopback; public TLS is delegated to a separately managed reverse proxy.
- No Docker socket is mounted into the API.
- No lab execution mode is enabled; production lab execution remains fail-closed until a separate reviewed sandbox service is deployed.
- OIDC membership is provisioned out of band; login does not grant a tenant role.

## Important database limitation

The current backend persistence implementation is SQLite. The named volume gives this single-node Compose example a persistent file location, but it does not provide multi-replica concurrency, managed database failover, point-in-time recovery or automatic backup scheduling. Do not scale this service horizontally. Schedule encrypted backups of the SQLite volume, run the repository backup/restore rehearsal, record RPO/RTO, and test restoration on a clean host.

PostgreSQL support is not implemented in this branch. A PostgreSQL deployment requires a repository-wide persistence adapter/migration, schema migration strategy and concurrency/tenant-isolation acceptance; do not point ARTIFICIAL_SCIENTIST_DB_PATH at a PostgreSQL URL.

## Operations still required

1. Provision a real API host and bind-mount/backup strategy.
2. Provision DNS and the HTTPS reverse proxy; test TLS renewal and security headers.
3. Configure the OIDC provider, public SPA client, CORS, exact callback URI and API audience.
4. Run backend/scripts/provision_tenant.py against the API database to provision the first tenant admin.
5. Run the live OIDC protocol tests, including invalid tokens, unknown kid, key rotation and tenant revocation.
6. Run the sandbox adversarial acceptance protocol in docs/release/PRODUCTION_VALIDATION_RUNBOOK.md using an isolated worker service; do not mount the host Docker socket into the API.
7. Configure and test monitoring, alerts, audit retention, incident response, backup/restore and rollback.
8. Obtain independent security and domain-expert scientific validation.

No production deployment, DNS change, secret creation, tenant-admin assignment or paid infrastructure provisioning is performed by this repository change.
