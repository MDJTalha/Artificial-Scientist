# PostgreSQL Migration Architecture and Acceptance Plan

**Status:** design decision proposed; implementation and production cutover are not complete  
**Scope:** persistence used by the lab, research-record and bounded-autonomy subsystems  
**Parent work:** PR #44 owner onboarding guide  
**Decision owner:** ASDS repository owner  
**Last updated:** 2026-11-01

## 1. Executive decision

ASDS must not be migrated by changing `ARTIFICIAL_SCIENTIST_DB_PATH` to a PostgreSQL URL or by swapping SQLite's connection function. The current stores embed SQLite-specific SQL, transaction semantics, schema inspection, triggers, and binary handling.

Adopt a staged persistence boundary using **SQLAlchemy 2.x Core + Alembic + psycopg 3** for the PostgreSQL implementation. Keep the current SQLite stores operational during the transition. Prefer SQLAlchemy Core over an ORM rewrite: the stores are explicit repositories with domain-specific transaction and integrity rules, and a wholesale ORM conversion would enlarge the change surface without improving the migration guarantees.

This is an architecture proposal, not an authorization to provision a database or migrate production data.

## 2. Current-state inventory

The inspected implementation has three independent SQLite persistence areas:

| Store | Current responsibility | SQLite-specific dependencies / semantics |
|---|---|---|
| `lab/store.py` | Lab runs, execution attempts, JSON and binary artifacts, retention events, per-tenant quotas | `sqlite3`, `PRAGMA foreign_keys`, `BEGIN IMMEDIATE`, `sqlite3.Row`, `PRAGMA table_info`, SQLite DDL/check constraints, BLOB |
| `records/store.py` | Append-only research records, audit events, source identity, schema versioning and legacy source backfill | `sqlite3`, `PRAGMA user_version`, `PRAGMA table_info`, `INSERT OR IGNORE`, SQLite triggers, SQLite DDL |
| `autonomy/store.py` | Tenant-owned workflows, transitions, checkpoints and versioned memory | `sqlite3`, `executescript`, `PRAGMA busy_timeout`, `BEGIN IMMEDIATE`, SQLite uniqueness and transaction behavior |

The stores currently accept filesystem paths, and the backend dependency list does not include SQLAlchemy, Alembic or a PostgreSQL driver. The lab and record stores also perform important integrity, append-only, ownership and quota checks which must survive the move.

## 3. Target architecture

### 3.1 Configuration and repository selection

Introduce one explicit backend configuration contract:

- `ARTIFICIAL_SCIENTIST_DATABASE_URL`: PostgreSQL SQLAlchemy URL, supplied only through server-side deployment secrets.
- `ARTIFICIAL_SCIENTIST_DATABASE_BACKEND`: explicit `sqlite` or `postgresql`; no implicit inference from a URL in production.
- `ARTIFICIAL_SCIENTIST_DB_PATH`: retained only for the SQLite backend and backward compatibility during the transition.
- `ARTIFICIAL_SCIENTIST_DATABASE_POOL_SIZE` and `ARTIFICIAL_SCIENTIST_DATABASE_MAX_OVERFLOW`: optional bounded pool settings, with conservative defaults documented per deployment.

Production must fail closed if the backend is PostgreSQL but the URL is absent, malformed, or uses an unsupported scheme. Never log the URL, credentials, query string or connection exception text if it could contain secrets.

Keep public API and domain models independent of SQLAlchemy. A small persistence factory selects repository implementations at application startup. Do not add a runtime fallback from a failed PostgreSQL connection to SQLite: that would split writes and create a false durability guarantee.

### 3.2 Connection lifecycle

Use SQLAlchemy Core with a synchronous `Engine` initially, matching the current synchronous store methods. Configure:

- bounded connection pool and overflow;
- `pool_pre_ping=True`;
- explicit connect and statement timeouts;
- TLS certificate verification for hosted PostgreSQL;
- server-side least-privilege database credentials;
- transaction scopes around each existing atomic repository operation;
- health/readiness checks that distinguish process liveness from database readiness.

Do not enable broad network access or place credentials in frontend variables. Avoid serverless connection exhaustion: provider pooler or a bounded application pool must be selected based on the chosen provider's documented connection model.

### 3.3 Schema and type mapping

Use Alembic revisions as the authoritative PostgreSQL schema history. Keep migration revisions deterministic and reviewed.

| Existing data | PostgreSQL representation | Preservation requirement |
|---|---|---|
| UUID/text identifiers | `TEXT` initially (or `UUID` only after compatibility tests) | Preserve exact identifier values and API serialization |
| UTC ISO timestamps | `TIMESTAMPTZ` after explicit parse/normalization | Preserve instants; normalize all writes to UTC |
| canonical JSON payloads | `TEXT` initially; optional `JSONB` projection later | Keep original canonical bytes/string for SHA-256 verification |
| artifact binary payloads | `BYTEA` | Exact byte-for-byte digest and size match |
| boolean/integer flags | `BOOLEAN` / `BIGINT` or `INTEGER` | Preserve values and range constraints |
| nullable tenant IDs | nullable `TEXT` | Legacy NULL ownership remains NULL; never guess tenant assignment |

Do not replace checksum-covered JSON text with PostgreSQL's re-serialized JSONB representation. JSONB may be added as a non-authoritative query projection only if the canonical source remains intact.

### 3.4 Constraints, indexes and append-only controls

Recreate all primary keys, foreign keys, uniqueness rules, check constraints and tenant-leading indexes in Alembic migrations. In particular:

- lab artifacts retain foreign-key ownership to their lab run and existing size/type constraints;
- source identity remains unique and append-only;
- research records and audit events remain append-only;
- autonomy memory uniqueness remains scoped by tenant, key and version;
- all tenant-scoped reads and writes include tenant ownership in predicates;
- PostgreSQL triggers or narrowly scoped database permissions must enforce append-only invariants even if application code is bypassed.

Review the PostgreSQL treatment of nullable columns in unique constraints before translating SQLite constraints. Preserve the current semantics intentionally; do not rely on accidental engine differences.

## 4. Transaction and concurrency mapping

Do not mechanically translate `BEGIN IMMEDIATE`. PostgreSQL uses MVCC and row/table locks rather than SQLite's database-wide write reservation.

For each operation, define the invariant and select the narrowest safe mechanism:

- **Lab quota reservation:** perform quota read and reservation in one transaction using a tenant-scoped counter/reservation row locked with `SELECT ... FOR UPDATE`, or a serializable transaction with bounded retry. A plain `COUNT(*)` followed by insert is race-prone under concurrent requests.
- **Autonomy workflow transition/approval:** use a conditional `UPDATE ... WHERE workflow_id = ... AND tenant_id = ... AND state = ...`; require exactly one affected row; insert the transition event in the same transaction.
- **Memory version allocation:** lock a tenant/key allocation row or use a database-enforced unique key plus retry on conflict. Do not use an unlocked `MAX(version)+1` under concurrent writers.
- **Record plus audit event:** insert both in a single transaction; any audit insert failure rolls back the record insert.
- **Source deduplication:** rely on a unique identity constraint and translate unique violations into the existing domain-level duplicate-source error.
- **Retention:** delete artifacts/run data and write the retention event atomically, preserving the current audit trail and foreign-key behavior.

Define retry policy only for known transient SQLSTATEs (e.g. serialization failure/deadlock), with bounded attempts, jitter and idempotency. Never retry integrity violations as if they were transient.

## 5. Migration and rollback plan

### Phase A — compatibility foundation

1. Add the SQLAlchemy Core engine factory and URL validation.
2. Add Alembic and an initial PostgreSQL schema revision.
3. Keep SQLite as the default for existing tests and local development.
4. Add PostgreSQL repository implementations behind the existing store interfaces.
5. Add contract tests that run the same repository behavior against SQLite and a real PostgreSQL service.

Exit criteria: all repository contract tests pass on both engines; no production configuration change.

### Phase B — export, import and verification tooling

Create an explicit operator-invoked migration command with:

- source database opened read-only;
- consistent SQLite snapshot/backup before export;
- stable table ordering respecting foreign keys;
- deterministic batch sizes and restart checkpoints;
- dry-run mode by default;
- per-table row counts, null-tenant counts, byte totals and content-hash totals;
- per-record and per-artifact SHA-256 verification;
- duplicate/constraint conflict report that stops rather than silently dropping or rewriting records;
- no tenant backfill or data transformation;
- explicit `--apply` confirmation for writes to the target;
- redacted logs with no payloads, tokens, credentials or full connection strings.

Migration must be restartable and idempotent. A repeated batch must not duplicate records or audit events. Preserve original record IDs, event IDs, timestamps and canonical payloads.

### Phase C — shadow validation

1. Take a verified snapshot.
2. Import into a non-production PostgreSQL database.
3. Run read-only comparison checks across all tables.
4. Run application repository contract and concurrency tests against PostgreSQL.
5. Compare representative API responses and integrity verification results.
6. Exercise backup and restore into a fresh database.

Do not dual-write to SQLite and PostgreSQL as an uncoordinated application-level strategy. If shadow reads are used, keep PostgreSQL writes isolated to the migration/test environment until consistency and rollback are proven.

### Phase D — controlled cutover

1. Obtain owner approval and a maintenance window.
2. Stop or drain all writers.
3. Take a final consistent backup and record its digest.
4. Import final delta and run full verification.
5. Change server-side database configuration only.
6. Run readiness, tenant-isolation, append-only, artifact retrieval and workflow-transition smoke tests.
7. Keep the old SQLite snapshot read-only and retained under the approved retention policy.
8. Roll back by restoring the old deployment/configuration only if no PostgreSQL-only writes have been accepted; otherwise execute a documented reverse-reconciliation plan.

No cutover until restore and rollback have been rehearsed successfully.

## 6. Required test matrix

| Area | Required PostgreSQL test |
|---|---|
| Store contract | Same create/read/list/error behavior as SQLite |
| Integrity | Canonical JSON and artifact digests match persisted bytes |
| Foreign keys | Orphan artifact and audit references are rejected |
| Append-only | UPDATE/DELETE attempts rejected at DB layer |
| Tenant isolation | Cross-tenant read/write attempts return no data and cannot mutate |
| Legacy ownership | NULL tenant rows remain inaccessible to tenant-scoped queries |
| Concurrency | Competing lab quota reservations cannot exceed quota |
| Concurrency | Competing workflow transitions allow exactly one valid transition |
| Concurrency | Concurrent memory writes allocate unique ordered versions |
| Idempotency | Replayed migration batch does not duplicate records/events |
| Resilience | Pool exhaustion, connection loss and transaction rollback are bounded and observable |
| Backup/restore | Restore to a clean target reproduces counts, digests and application reads |
| Security | TLS verification, least privilege, secret redaction and no public DB exposure |

Tests must use an actual PostgreSQL service (container or managed ephemeral instance), not SQLite with a PostgreSQL URL.

## 7. Security and operations requirements

- Database URL exists only in backend runtime secret configuration.
- Never expose database URL or credentials through Vite `VITE_*` variables, frontend bundles, logs, PR comments or issue text.
- Use separate least-privilege migration and application roles.
- Restrict database ingress to the application and approved operator paths.
- Require TLS with certificate verification.
- Establish backup frequency, retention, restore objectives (RPO/RTO), alerting and ownership before production selection.
- Verify tenant filters in repositories and authorization middleware; PostgreSQL Row-Level Security may be evaluated as defense in depth, not as a substitute for correct application authorization.
- Keep migration, backup and restore operations auditable.

## 8. Acceptance gates and ownership

| Gate | Evidence | Owner |
|---|---|---|
| Architecture | Approved persistence boundary and schema mapping | ASDS maintainers |
| Implementation | PostgreSQL stores, Alembic revisions and passing contract tests | Engineering |
| Data integrity | Export/import reports with matching counts and hashes | Engineering + operator |
| Concurrency | Race tests against real PostgreSQL | Engineering |
| Recovery | Successful restore drill and measured RPO/RTO | Operator |
| Security | Secret, TLS, role, network and tenant-isolation review | Independent security reviewer |
| Cutover | Signed maintenance/cutover approval | Repository owner |

## 9. Explicit non-claims

This document does not mean that:

- PostgreSQL has been provisioned or selected for production;
- any database credentials or connection URLs exist;
- SQLite data has been migrated;
- PostgreSQL repository code or migrations have been implemented;
- backup/restore, concurrency, performance or security tests have passed;
- production readiness or certification has been achieved.

**Next implementation unit:** add the engine/configuration boundary and Alembic baseline in a separate code PR, then migrate one store at a time behind contract tests. Do not combine all three stores and data cutover into one change.
