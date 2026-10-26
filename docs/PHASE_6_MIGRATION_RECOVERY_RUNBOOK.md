# Phase 6 — Production Migration, Backup, Restore, and Rollback Rehearsal

**Status: runbook defined; production rehearsal NOT performed.**
This runbook is a controlled acceptance procedure. The automated SQLite snapshot rehearsal is a preflight and does not replace a production-like backup/restore drill.

## 1. Safety and ownership

- Name a change owner, database owner, application owner, operator, reviewer, and rollback decision-maker.
- Obtain written approval for the rehearsal window and the sanitized snapshot source.
- Use only a sanitized, access-controlled representative snapshot. Never place production customer data or credentials in Git, pull-request comments, CI artifacts, or this evidence record.
- Record source environment, snapshot timestamp, deployed commit, schema version, database size, row counts by relevant table, WAL/journal mode, and attachment-storage inventory.
- Confirm the backup destination is encrypted, access-restricted, monitored, and has sufficient capacity.
- Do not apply legacy ownership claims to the source database. Claims must use an explicit reviewed manifest and a copied rehearsal database.
- Stop if data provenance, backup consistency, storage inventory, or ownership mapping cannot be established.

## 2. Preflight

1. Identify the exact migration revision and command. Review every schema change and verify it is additive or has a documented reversible strategy.
2. Inventory all data-bearing components: SQLite database, WAL/SHM/journal files, binary attachment directory/object store, configuration references, and external records used to reconcile artifacts.
3. Capture baseline counts and integrity checks for tenants, principals, memberships, lab runs, execution attempts, JSON artifacts, binary artifact metadata, audit events, and unowned legacy rows.
4. Generate and independently review the explicit legacy ownership manifest. Reject duplicate IDs, unknown tenants, unknown records, and conflicting assignments. Keep ambiguous historical records unowned and inaccessible; never guess ownership.
5. Verify the restore procedure in an isolated location before the maintenance window. Confirm disk space, permissions, encryption, and access controls.
6. Agree on measurable abort thresholds for migration duration, restore duration, missing records, integrity mismatches, and unexpected ownership changes.

## 3. Consistent backup and WAL handling

1. Quiesce writes or use the database's documented consistent-backup mechanism. For SQLite, prefer the SQLite backup API or an equivalent coordinated snapshot procedure; do not copy only the main database file while uncheckpointed WAL data may exist.
2. Record backup method, timestamp, source identity, file size, checksum, and whether WAL/journal state was included or safely checkpointed.
3. If using filesystem-level snapshots, follow SQLite consistency requirements and capture all files needed for a consistent state. Do not assume a raw copy of the .sqlite3 file alone is sufficient.
4. Back up binary attachment storage and metadata as a coordinated set. Verify referenced attachments exist and SHA-256/size matches metadata where applicable.
5. Store a read-only backup copy separately from the rehearsal target. Do not overwrite the only recovery copy during tests.
6. Record backup completion and the operator who verified it.

## 4. Rehearsal execution

Run in an isolated production-like environment with the same application revision, schema migration code, runtime versions, and relevant configuration behavior as the proposed deployment.

1. Restore the consistent backup to a new rehearsal target. Verify database integrity and baseline record counts before migration.
2. Run the automated Phase 6 rehearsal tool against a copy only:

   python -m artificial_scientist.phase6_rehearsal --database PATH --manifest claims.json --operator-principal-id UUID

   Confirm the source path is not the apply target. The tool's temporary SQLite snapshot and claim audit checks are preflight evidence, not proof of deployment backup/restore readiness.
3. Run schema migration and application startup checks. Record exact commands, exit codes, elapsed time, logs with secrets redacted, and resulting schema version.
4. Verify legacy rows without manifest entries remain unowned and tenant-inaccessible. Verify explicit claims map only to approved tenant IDs and run/attempt ownership stays consistent.
5. Run the full backend test suite and targeted migration, legacy-claim, tenant-isolation, audit, and artifact-integrity tests on the migrated copy.
6. Verify expected records, row counts, ownership invariants, audit events, artifact checksums, and attachment references. Explain any count difference; unexplained loss or reassignment is a failure.
7. Exercise read/write smoke tests under the approved test identity and verify tenant A cannot access tenant B data.
8. Record total outage/maintenance time and application recovery time. If online migration is intended, test the actual traffic/drain strategy; do not infer zero downtime from an offline rehearsal.

## 5. Restore and rollback drill

A migration is not accepted until restore and rollback are exercised, not just described.

1. Preserve the pre-migration backup as immutable recovery input.
2. Introduce a controlled rehearsal failure after migration in the isolated environment.
3. Follow the documented rollback decision: stop writes, switch application traffic away from the failed target, restore the known-good backup into a fresh target, restore the matching attachment snapshot, and validate checksums/counts.
4. Verify the recovered application starts and reads known records, preserves tenant isolation, and has no cross-version schema mismatch.
5. Compare pre-migration and restored record counts, key identifiers, attachment hashes, and audit continuity. Record events written after backup and the approved reconciliation policy; do not silently discard them.
6. Record measured recovery time and data-loss window (RTO/RPO). Compare them with owner-approved targets.
7. Verify the original backup remains intact and the failed rehearsal target is retained or securely disposed of under the evidence/retention policy.
8. If rollback cannot restore a consistent database plus attachment set within approved targets, fail the rehearsal and block rollout.

## 6. Required acceptance evidence

- [ ] Approved change record and named accountable owners.
- [ ] Sanitization attestation and snapshot provenance.
- [ ] Exact application commit, migration revision, schema version, runtime versions, and command log.
- [ ] Pre-migration backup method, timestamp, checksum, integrity result, and storage location reference.
- [ ] WAL/journal handling and attachment backup evidence.
- [ ] Baseline and post-migration table counts and integrity results.
- [ ] Legacy ownership manifest review and hash; manifest contains IDs only, no credentials or personal data.
- [ ] Automated rehearsal result plus full production-like migration result.
- [ ] Tenant-isolation and artifact-integrity acceptance results.
- [ ] Controlled failure/rollback result, restore checks, measured RTO/RPO, and comparison to approved targets.
- [ ] Downtime/maintenance duration and operator timeline.
- [ ] Independent reviewer sign-off and approved exceptions.
- [ ] Evidence repository/location: NOT YET RECORDED.
- [ ] Rehearsal date, operators, reviewer, actual results: NOT YET RECORDED.

## 7. Pass/fail and abort criteria

**Pass** only if backup is consistent and recoverable; migration is repeatable; no unexplained record, audit, ownership, or artifact-integrity differences exist; rollback restores a usable, tenant-isolated system; measured RTO/RPO meet approved targets; and an independent reviewer signs the evidence.

**Abort and block release** if there is no sanitized representative snapshot, no explicit ownership manifest, a backup/restore checksum or integrity failure, unexplained row-count drift, ambiguous ownership assignment, cross-tenant access, broken attachment references, missing audit continuity, rollback failure, or absent sign-off.

## 8. Current evidence state

- Automated rehearsal code exists and is covered by repository tests, as documented in docs/PHASE_6_COMPLETION_MATRIX.md.
- A real production-like sanitized snapshot rehearsal, restore drill, WAL/attachment recovery validation, downtime measurement, rollback exercise, and independent sign-off are NOT established by this document.
- Production migration/recovery acceptance remains BLOCKED / NOT VERIFIED until the evidence above is collected and reviewed.