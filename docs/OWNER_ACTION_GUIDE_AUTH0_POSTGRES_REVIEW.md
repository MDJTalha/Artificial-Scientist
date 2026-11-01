# ASDS Owner Action Guide — Auth0, PostgreSQL and Independent Review

**Prepared:** 2026-11-01  
**Applies to:** Workstreams 4, 5, 7, 8 and 9  
**Purpose:** Turn owner decisions into safe, verifiable next actions. This guide does not authorize production changes or certify the system.

## Owner decisions recorded

- Auth0: an existing tenant is available.
- PostgreSQL: request a low-cost recommendation.
- Infrastructure budget: limited; prefer free or usage-based non-production resources and avoid idle paid infrastructure.
- Independent reviewers: not yet identified; assistance is required.

## 1. Auth0 — confirm the existing tenant

The current repository example files contain the following suggested defaults. They are configuration examples, **not proof that the live Auth0 tenant or application is configured correctly**:

- Example issuer/domain: `https://asds-artificial-scientist.us.auth0.com/`
- Example SPA Client ID: `a0Jm8oh05S1V4hMOg0v2d84MNO56zJX8`
- Backend JWKS URL pattern: `https://<tenant-domain>/.well-known/jwks.json`

The owner must confirm these values in the Auth0 Dashboard before they are used in a deployment. Do not create a second tenant unless the existing tenant is inaccessible or unsuitable.

### Dashboard checklist

1. Open the existing Auth0 tenant and confirm its exact tenant domain.
2. Open **Applications → Applications** and confirm the ASDS Single Page Application (SPA) client. Confirm the Client ID matches the repository example or update the deployment value.
3. Open **Applications → APIs**. Confirm an API exists for ASDS. If not, create one with a deliberate, stable API Identifier. The API Identifier is the JWT audience; it is not the SPA Client ID.
4. Define only the scopes the API actually requires. Do not invent a scope name merely to satisfy a configuration variable.
5. Configure Authorization Code Flow with PKCE for the SPA. Do not create or embed a browser client secret.
6. Add only the exact HTTPS callback, logout and web origins used by the approved Vercel preview/production deployments. Do not use wildcard origins.
7. Ensure the backend issuer, audience, JWKS URL and CORS origins match the dashboard configuration.
8. Provision the test user's tenant membership through the approved backend administration/bootstrap process. A browser-supplied tenant ID is not proof of membership.

### Repository environment variable names

Backend (`backend/.env.example`):
- `ARTIFICIAL_SCIENTIST_OIDC_ISSUER`
- `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE`
- `ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL`
- `ARTIFICIAL_SCIENTIST_OIDC_REQUIRED_SCOPE` (only if the exact scope is defined)
- `ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS`

Frontend (`frontend/.env.example`):
- `VITE_AUTH0_DOMAIN`
- `VITE_AUTH0_CLIENT_ID`
- `VITE_AUTH0_AUDIENCE`
- `VITE_API_BASE_URL`
- `VITE_ASDS_TENANT_ID`

The Vite values are public browser configuration, not secrets. Never place a client secret, database password, signing key or access token in a `VITE_*` variable.

### What the owner should send to the engineering team

Send only these non-secret values after checking them in Auth0:
- Exact tenant domain (for example, `tenant-region.auth0.com`).
- Exact API Identifier/audience.
- SPA Client ID (public identifier).
- Exact scopes defined on the API.
- Approved preview and production frontend origins.
- The test tenant ID to which the test principal should belong, if already provisioned.

Do **not** send passwords, client secrets, refresh tokens, access tokens, private keys or database connection strings in chat, issues, commits or pull-request comments. Enter secrets only into the intended provider's protected environment-variable/secret manager interface.

### Live acceptance gate

A live integration is not complete until a deployed test demonstrates valid access-token acceptance and rejection of absent, malformed, expired, wrong-issuer, wrong-audience, invalid-signature and insufficient-scope tokens; verifies JWKS rotation behavior, CORS, membership revocation and cross-tenant denial; and records the deployment SHA and configuration revision without storing tokens.

## 2. PostgreSQL — low-cost provider recommendation

### Recommendation

Use **Neon Free for disposable development and CI integration experiments only**, subject to a usage-limit check. It provides a managed PostgreSQL endpoint and branching that can support isolated test databases. The current published Free plan includes 1 GB storage per project and 100 compute-hours per project per month, and compute scales to zero after inactivity. Those characteristics make it useful for development, not a production durability guarantee. See [Neon plans](https://neon.com/docs/introduction/plans).

For a low-budget production candidate, compare:
- **Neon Launch:** usage-based with no monthly minimum; evaluate the actual expected compute, storage, restore and support costs. Do not assume it includes an uptime SLA.
- **Supabase Pro:** currently advertised from USD 25/month, with daily backups retained for 7 days and an 8 GB database allowance on the plan page. This is easier to budget, but confirm region, backup/restore objectives, networking and contractual support before selecting it. See [Supabase pricing](https://supabase.com/pricing).

**Provisional choice:** Neon for non-production engineering now; no production provider is approved yet. Do not store production research records on a free tier. Before production selection, compare data residency/region, TLS, connection pooling, compute availability, backup retention, point-in-time recovery, restore testing, support/SLA, egress, and total monthly cost. Select the least expensive option that satisfies the agreed recovery-point and recovery-time objectives—not simply the lowest advertised entry price.

### Why implementation must precede a DATABASE_URL switch

The current persistence modules use SQLite-specific `sqlite3`, `PRAGMA`, SQLite DDL and transaction behavior. Adding a PostgreSQL URL or driver alone will not make the application PostgreSQL-compatible.

The engineering sequence is:
1. Inventory all stores and their transactional invariants.
2. Select a driver and migration framework.
3. Define storage/transaction boundaries.
4. Implement and test PostgreSQL persistence for each production-critical store.
5. Add versioned migrations and an explicit legacy-data ownership reconciliation process.
6. Run integration tests against a real PostgreSQL service in CI.
7. Rehearse sanitized migration, checksum/row-count reconciliation, tenant isolation, backup and restore.
8. Obtain owner approval before migrating any real data or routing production traffic.

Legacy rows with unknown tenant ownership must remain unassigned and inaccessible until explicitly reconciled. Never infer ownership from email, record contents or timestamps.

## 3. Independent security assessor — how to identify one

The assessor must be independent of the implementation team and have demonstrable experience in application security and cloud-native systems. Prefer a qualified application penetration-testing firm or senior independent security consultant with relevant references and a written scope.

Minimum selection criteria:
- Demonstrated API security, OAuth2/OIDC and JWT expertise.
- Multi-tenant authorization testing (BOLA/IDOR, privilege escalation and tenant boundary tests).
- Python/FastAPI and cloud deployment/container security experience.
- Secure data migration, PostgreSQL and backup/restore review experience.
- Container/microVM isolation, Linux namespaces, seccomp and network-egress testing experience for the sandbox scope.
- Written methodology, severity ratings, reproducible findings, remediation guidance and retesting.
- Clear independence/conflict-of-interest statement and secure handling of test data.

Request a fixed-scope proposal in stages if budget is constrained:
1. Architecture/threat-model review and focused API authorization assessment.
2. PostgreSQL migration and data-isolation review.
3. Sandbox adversarial testing before enabling untrusted execution.
4. Final release-candidate retest.

Do not grant production credentials or real research data by default. Use a disposable staging environment, synthetic tenants and test identities. The assessor's report must identify the exact commit and deployment reviewed.

## 4. Scientific expert validation — reviewer profile

Identify at least one domain expert for each initial scientific benchmark area. A suitable reviewer should have relevant publications or professional research experience, be able to define accepted reference cases, and be willing to challenge results rather than merely endorse the platform.

Ask reviewers to:
- Review the benchmark protocol before execution.
- Supply or approve reference problems with known/independently established outcomes.
- Define acceptable error, uncertainty and reproducibility criteria.
- Inspect raw outputs, provenance, source quality and failed/negative cases.
- Re-run selected cases independently using pinned inputs/configuration.
- Document limitations, disagreements and conflicts of interest.

No reviewer should be asked to certify broad scientific discovery capability from a product demonstration. Validation claims must be restricted to the exact benchmark, model/configuration, version and test results reviewed.

## 5. Release approval boundary

The AI engineering agent can prepare implementation, automated tests and evidence. It cannot substitute for:
- Owner-controlled Auth0 and cloud configuration.
- Owner authorization for production resource creation or data migration.
- Independent security assessment.
- Independent scientific replication/expert review.
- Owner approval of the production release.

Workstream 9 remains blocked until the evidence register in `docs/PRODUCTION_READINESS_WORKSTREAMS_4_9.md` contains the required evidence and authorized approvals.

## 6. Immediate owner action

The next useful owner contribution is to verify the existing Auth0 tenant and return the non-secret values listed in Section 1. In parallel, choose whether to create a Neon **development/staging-only** project for integration testing. Do not create a production database or paste a connection string into GitHub.

## Provider references

- [Neon plans and limits](https://neon.com/docs/introduction/plans)
- [Supabase pricing and backup plan details](https://supabase.com/pricing)
