# ASDS Production Readiness — Workstreams 4–9

**Status date:** 2026-11-01  
**Scope:** Workstreams 4 through 9 in the current engineering status.  
**Release posture:** All six workstreams remain open until their evidence and approvals are recorded. This plan is not a certification.

## Decision and execution principles

1. Keep all protected capabilities fail-closed until their prerequisites are met.
2. Do not copy secrets, tokens, private connection strings, or real research data into GitHub issues, commits, CI logs, or this evidence register.
3. Separate code-level tests from live-environment evidence and independent sign-off.
4. Pin every result to an immutable commit, deployment, configuration version, test-case version, and timestamp.
5. Do not represent a mock, local test, successful build, or AI code review as a live integration test or independent assessment.
6. Do not create production resources, migrate user data, change DNS, or enable public execution without explicit operator approval.

## Workstream 4 — Live Auth0 integration

**Current repository posture:** Generic OIDC/JWKS validation is implemented in the active backend change. The frontend is configured for Auth0 SPA login using Authorization Code Flow with PKCE. Actual tenant API Identifier, scopes, Vercel environment configuration, and real-token end-to-end evidence remain owner/environment dependent.

### Owner-provided configuration (never commit secrets)

- [ ] Confirm the Auth0 tenant domain and issuer.
- [ ] Create or confirm an Auth0 API; record its exact API Identifier (audience).
- [ ] Decide required API scopes and define them on the Auth0 API. Do not invent scopes.
- [ ] Confirm SPA Client ID and allowed callback/logout/web origins.
- [ ] Add exact Vercel Preview and Production origins to Auth0 allowlists.
- [ ] Set backend issuer, audience, JWKS URL, and exact CORS origins in the intended deployment environment.
- [ ] Set frontend public domain, SPA Client ID, audience and API base URL at build time.
- [ ] Provision an explicit server-side tenant membership for the test principal; a client-supplied tenant header is not authorization.

### Acceptance evidence

- [ ] SPA login uses PKCE; no client secret is present in browser code or Vite variables.
- [ ] Real access token is obtained for the configured API audience; ID token is not used as API bearer token.
- [ ] Deployed API accepts a valid signed access token and rejects absent, malformed, expired, wrong-issuer, wrong-audience, wrong-signature and missing-required-scope tokens.
- [ ] JWKS key rotation/unknown-key refresh behavior is exercised against the actual tenant.
- [ ] CORS preflight and browser requests succeed from each exact approved origin and fail from an unlisted origin.
- [ ] Membership revocation and cross-tenant access denial are demonstrated.
- [ ] Evidence records deployment ID, deployed commit SHA, Auth0 configuration revision, test case IDs, outcomes and timestamp. Never record the token.

**Release decision:** OPEN until all applicable checks above are completed against the real deployment.

## Workstream 5 — PostgreSQL durability and migration

**Current repository posture:** Stores use SQLite-specific APIs and SQL. A `DATABASE_URL` or PostgreSQL service alone does not provide PostgreSQL support. No production data migration is authorized by this plan.

### Engineering work required

- [ ] Inventory every persistence owner and table: research records, lab runs/attempts/artifacts/retention, tenant directory/memberships/audit, autonomy workflows/memory/checkpoints, and any auxiliary stores.
- [ ] Select the PostgreSQL driver and migration framework; document supported PostgreSQL versions and connection/pooling model.
- [ ] Introduce a storage interface with explicit transaction, isolation, locking, uniqueness, foreign-key and pagination semantics. Do not translate SQLite SQL mechanically without testing semantics.
- [ ] Implement PostgreSQL stores for every production-critical persistence domain, or keep the corresponding endpoints disabled.
- [ ] Add versioned, forward-only migrations and a tested rollback/restore strategy. Treat irreversible data transformations as separately approved operations.
- [ ] Preserve tenant ownership, content hashes, audit linkage, retention tombstones, artifact integrity and idempotency.
- [ ] Add concurrency tests for quotas, unique source identity, workflow transitions, membership changes and simultaneous writes.
- [ ] Add integration tests against an ephemeral real PostgreSQL instance in CI; SQLite tests are not substitutes.
- [ ] Verify connection limits, TLS, least-privilege database roles, statement timeouts, backup retention and restore objectives.

### Migration rehearsal evidence

- [ ] Sanitized snapshot ID and source schema version.
- [ ] Snapshot checksum and successful isolated restore.
- [ ] Dry-run output and row counts by table/tenant.
- [ ] Ownership reconciliation; unknown legacy ownership remains unassigned and inaccessible.
- [ ] Migration execution log and resulting schema version.
- [ ] Referential-integrity, digest, row-count and tenant-isolation reconciliation.
- [ ] Application smoke/regression tests against migrated copy.
- [ ] Rollback or restore-to-pre-migration demonstration.
- [ ] Operator approval and independent reviewer sign-off.

**Release decision:** OPEN. Do not route production traffic or migrate real tenant data until the PostgreSQL implementation and rehearsal are verified.

## Workstream 6 — Reviewed OS execution sandbox

**Current repository posture:** An adapter interface and fail-closed production selection exist. The local subprocess worker and POSIX rlimits are defense in depth, not an OS sandbox. The declared future sandbox adapter intentionally does not execute jobs.

### Engineering/deployment work required

- [ ] Choose the supported runtime (hardened container or microVM) and document its threat model.
- [ ] Separate control plane from execution plane; send immutable, bounded job envelopes to an isolated runner.
- [ ] Enforce non-root identity, read-only root filesystem, dedicated scratch, no host mounts/runtime socket, dropped capabilities, no-new-privileges and syscall policy.
- [ ] Deny network by default, including metadata endpoints, internal networks and host gateway.
- [ ] Pass no API, database, Auth0 or cloud credentials into the worker.
- [ ] Enforce CPU, memory, PID, disk, file-size, descriptor, concurrency and wall-clock limits at the OS/orchestrator layer.
- [ ] Verify immutable image/runtime digest, dependency inventory, vulnerability scan and patch process.
- [ ] Validate artifact input/output size, type, digest and provenance at the control-plane boundary.
- [ ] Implement cancellation, hard termination, bounded queueing, cleanup, audit and observable failure states.

### Adversarial acceptance evidence

- [ ] Host-file canary read/write attempt is denied.
- [ ] Network canary, metadata endpoint and internal-service access are denied.
- [ ] Worker cannot read API environment variables, secrets or database files.
- [ ] CPU, memory, PID, disk, file descriptor and output limits are enforced.
- [ ] Timeout, cancellation, crash, malformed output and runner loss terminate safely.
- [ ] Scratch data is removed and cannot be read by a subsequent job.
- [ ] Results/artifacts cannot cross tenant boundaries.
- [ ] Tests run in disposable staging; preserve commands, runtime digest, logs and outcomes.
- [ ] Independent security reviewer signs off the runtime profile and residual risks.

**Release decision:** OPEN. Arbitrary/generated code remains disabled until this evidence exists.

## Workstream 7 — Independent security assessment

An independent assessment must be performed by a qualified reviewer who is not the implementation author and who can inspect the exact release candidate and deployment configuration. Automated tests and AI code review are supporting evidence only.

### Required scope

- [ ] AuthN/AuthZ, OIDC/JWKS validation, token handling, session and secret boundaries.
- [ ] Tenant isolation across every record, lab, artifact, memory, workflow, export and audit endpoint.
- [ ] Role grants/revocation, least privilege, privilege escalation and IDOR/BOLA.
- [ ] SQL/data integrity, migration, backup/restore and concurrency/race behavior.
- [ ] Audit integrity, access, retention, tamper detection and failure behavior.
- [ ] Sandbox escape, network egress, metadata access, filesystem and resource exhaustion.
- [ ] Dependency/supply-chain, container/image provenance, CI permissions and deployment configuration.
- [ ] CORS, TLS, rate limits, abuse controls, logging/PII leakage and incident response.
- [ ] Threat-model review and residual-risk acceptance.

### Required report

Record assessor identity/organization, independence statement, scope, exact commit and deployment IDs, methodology, test dates, findings with severity and reproduction evidence, remediation owner, retest result, residual risks and signed conclusion. Do not call the system independently assessed until the report and retest evidence exist.

**Release decision:** OPEN pending independent assessment and remediation closure.

## Workstream 8 — Scientific replication and expert validation

Scientific evaluation must test scientific outputs, not just API correctness or model fluency. Expert reviewers must be identified by relevant domain and conflicts of interest disclosed.

### Benchmark protocol

- [ ] Define versioned benchmark questions and expected evidence/answer criteria before running the candidate.
- [ ] Include supported, unsupported, contradictory and unavailable sources; misleading-source and prompt-injection cases.
- [ ] Include competing hypotheses, falsifiable predictions, null results and explicit uncertainty.
- [ ] Include numerical reference cases with tolerances and independent calculation where feasible.
- [ ] Include reproducibility cases: same immutable inputs/configuration, changed dependency/runtime, interrupted/recovered run.
- [ ] Include negative controls and known failure cases to detect false confidence.
- [ ] Freeze dataset provenance, licenses, inclusion/exclusion criteria and contamination controls.
- [ ] Pre-register scoring rubric, aggregation, failure handling and statistical analysis before evaluation.
- [ ] Run each case against a pinned commit, model/provider version, prompt/configuration digest and runtime manifest.
- [ ] Report raw case-level outcomes, failures, confidence/uncertainty, limitations and reproducibility instructions.

### Independent domain review

- [ ] Recruit qualified reviewers for each initially claimed scientific domain.
- [ ] Have reviewers assess source quality, method correctness, assumptions, calculations, falsifiability, novelty language and conclusions.
- [ ] Re-run selected experiments independently from the recorded configuration and artifacts.
- [ ] Record disagreements and negative results; do not average away critical scientific-integrity failures.
- [ ] Restrict public claims to the domains and capabilities actually evaluated.

**Release decision:** OPEN until benchmark execution, independent replication and domain-expert sign-off are recorded. No claim of Nobel-level performance, autonomous discovery, scientific truth or guaranteed novelty is supported by implementation status alone.

## Workstream 9 — Production release certification

Certification is a release decision over a specific immutable candidate, not a general statement about the repository.

### Mandatory evidence bundle

- [ ] Exact release commit, dependency lock state, build provenance and SBOM.
- [ ] Exact frontend/backend deployment IDs and deployed commit SHAs.
- [ ] Exact environment/configuration revision with secret values redacted.
- [ ] Green exact-SHA CI and integration/E2E test results.
- [ ] Live Auth0 validation and tenant-isolation evidence.
- [ ] PostgreSQL migration, backup/restore, recovery and operational rehearsal.
- [ ] Reviewed sandbox adversarial evidence.
- [ ] Independent security report and closed/retested critical/high findings.
- [ ] Scientific benchmark, replication and expert-review reports with limitations.
- [ ] TLS, secrets, least privilege, monitoring, alerting, rate limiting and incident-response evidence.
- [ ] Rollback plan, backup recovery objective, operational owner and on-call process.
- [ ] Explicit approval from the system owner and relevant independent reviewers.

### Release gate rules

- Any critical security finding blocks release.
- Any unresolved high-severity finding requires documented risk acceptance by the authorized owner and independent assessor; the default is to block.
- Missing identity, tenant isolation, durable storage or sandbox evidence blocks the affected protected capability.
- Missing scientific validation blocks scientific-performance claims and any autonomous research capability beyond the evaluated scope.
- A preview deployment is not a production release.
- No AI agent may issue its own independent security certification or scientific accreditation.

**Release decision:** BLOCKED until all applicable mandatory evidence is complete and signed.

## Evidence register template

Create one record per evidence item using this schema:

| Field | Required content |
|---|---|
| Evidence ID | Stable unique identifier |
| Workstream | 4, 5, 6, 7, 8 or 9 |
| Requirement | Exact checklist item |
| Candidate | Commit SHA and deployment ID |
| Method | Reproducible command/procedure and version |
| Result | Pass, fail, blocked or not applicable with rationale |
| Artifact | Link to sanitized report/log/test output |
| Owner | Responsible operator/engineer |
| Reviewer | Independent reviewer where required |
| Timestamp | UTC timestamp |
| Limitations | Scope and residual risk |
| Approval | Explicit sign-off and authority |

Never place credentials, raw tokens, private connection strings or sensitive research data in this register.

## Current disposition

| Workstream | Status | What can be done in repository | External dependency |
|---|---|---|---|
| 4 — Auth0 | Partially implemented; live verification open | Middleware/tests/config documentation | Owner confirms API Identifier/scopes; Auth0/Vercel configuration and live test |
| 5 — PostgreSQL | Outstanding | Storage abstraction, migrations, integration tests | Database provisioning, credentials, backups and rehearsal approval |
| 6 — OS sandbox | Adapter boundary implemented; sandbox open | Runner contract, tests and deployment manifests | Runtime provisioning and adversarial host/network tests |
| 7 — Security assessment | Not independently assessed | Remediation and evidence preparation | Qualified independent assessor |
| 8 — Scientific validation | Protocol documented; execution/expert sign-off open | Benchmark harness, versioned cases and reporting | Domain experts, independent replication and approved datasets |
| 9 — Production certification | Blocked | Release automation and evidence bundling | All preceding gates and owner approval |
