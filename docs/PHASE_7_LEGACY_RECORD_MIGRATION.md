# Phase 7 Legacy Research-Record Ownership Migration

## Purpose

Legacy research records created before tenant ownership was enforced have a `NULL` `tenant_id`. The API intentionally treats those records as unowned and does not expose them through tenant-scoped operations.

Ownership must never be inferred from payload content, request headers, filenames, source metadata, or the current operator's tenant.

## Controlled workflow

1. Take and retain a verified database backup.
2. Build an explicit JSON manifest containing only `record_id` and `tenant_id`.
3. Review the manifest independently before execution.
4. Run the command without `--apply` first. The default is dry-run.
5. Confirm every target record exists, the target tenant exists, and no existing ownership conflicts are reported.
6. Apply with an existing operator principal UUID.
7. Verify tenant-scoped reads/lists and source-identity lookups after the change.
8. Verify the `legacy:record-claim` security-audit events.
9. Retain the manifest, dry-run output, apply output, database backup, and verification results as release evidence.

## Command

Use:

python -m artificial_scientist.records.legacy_claim --database <path> --manifest <file>

For the controlled apply:

python -m artificial_scientist.records.legacy_claim --database <path> --manifest <file> --apply --operator-principal-id <uuid>

The apply operation is transactional. Research-record append-only triggers and source-identity append-only triggers are temporarily removed inside the same transaction only to perform the ownership migration, then recreated before commit. A failure rolls the transaction back.

## Release evidence

A production migration is not considered complete until the following are retained:

- sanitized representative database snapshot;
- reviewed ownership manifest;
- successful dry-run output;
- successful apply output;
- post-migration record counts and integrity checks;
- cross-tenant isolation checks;
- source-identity checks;
- security-audit event verification;
- operator identity and timestamp;
- measured backup/restore and rollback evidence;
- independent reviewer sign-off.

This document and the migration command are an execution mechanism and acceptance protocol. They do not constitute evidence that a production migration has already been performed.
