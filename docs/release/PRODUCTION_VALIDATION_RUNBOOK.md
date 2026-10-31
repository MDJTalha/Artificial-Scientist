# Production Validation Runbook

This runbook is the execution package for the external release gates. It distinguishes prepared/automatable work from evidence that can only be produced by the real deployment and independent reviewers.

## Gate 1 — OS-level laboratory sandbox

A dedicated sandbox runtime (container/VM/microVM or equivalent) must execute laboratory workloads with no host filesystem access except an ephemeral work directory, no host network by default, no inherited credentials, non-root identity, read-only application image/filesystem, ephemeral output storage, CPU/memory/process/file/wall-clock limits, syscall/capability restrictions, deterministic cleanup, and a separate runtime identity.

The application already fails closed when no reviewed adapter is configured. Do not enable local-process execution in production.

Acceptance protocol:
1. Record runtime/image digest and exact configuration.
2. Run an allowed mathematical operation and retain its result digest.
3. Attempt filesystem traversal outside the sandbox workspace.
4. Attempt access to cloud/service credentials.
5. Attempt loopback and external network access.
6. Attempt process creation/fork amplification.
7. Attempt oversized file creation.
8. Exceed the wall-clock deadline.
9. Force an abnormal worker exit.
10. Run concurrent jobs from two tenants and verify filesystem/artifact separation.
11. Verify cleanup after every pass/fail/timeout.
12. Repeat after restart.

Pass condition: every forbidden action is denied and every allowed action remains reproducible. Any host escape, credential exposure, cross-tenant artifact access, or cleanup failure is a release blocker.

## Gate 2 — Live OIDC/JWKS

Configure ARTIFICIAL_SCIENTIST_OIDC_ISSUER, ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE, and ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL.

Acceptance protocol:
- valid token;
- expired token;
- wrong issuer;
- wrong audience;
- altered signature;
- unknown kid;
- JWKS refresh after key rotation;
- multi-audience token with expected audience;
- missing sub;
- malformed token;
- disabled/revoked identity;
- tenant membership mismatch;
- TLS certificate failure.

Retain provider identifier, key IDs before/after rotation, timestamps, HTTP status, and sanitized outcomes. Never store bearer tokens in evidence.

## Gate 3 — Migration and recovery

Use a sanitized production-shaped snapshot.

1. Checksum source snapshot.
2. Create immutable backup.
3. Restore backup to a clean target.
4. Run migrations.
5. Start the application.
6. Execute tenant authorization/read/write checks.
7. Verify row counts, ownership, checksums and audit records.
8. Simulate a failed migration.
9. Verify rollback/no partial ownership changes.
10. Restore from backup again.
11. Record recovery time and data-loss window.

For PostgreSQL, include WAL/PITR rehearsal if used in production. For SQLite deployments, use the repository backup/restore helper plus filesystem-level backup controls.

## Gate 4 — Independent security review

The reviewer must be independent of implementation decisions. Scope: authentication/OIDC/JWKS, authorization and tenant isolation, privilege escalation, API abuse/rate limits, secrets, dependency/supply-chain posture, audit integrity, sandbox boundary, database/network/deployment, logging and incident response.

Retain signed findings, severity, remediation status, residual risk and reviewer identity.

## Gate 5 — Operational deployment

Verify TLS and secure headers; secret manager integration; least-privilege service identity; network segmentation/firewall; health/readiness; monitoring and alerting; structured logs/audit retention; quotas/rate limits; backup and restore; deployment rollback; configuration drift detection; incident response.

## Gate 6 — Scientific validation

Use a version-pinned benchmark corpus and retain raw outputs.

Evaluate numerical correctness, symbolic correctness, unit conversion, reproducibility, provenance/evidence preservation, unsupported-claim resistance, prompt-injection resistance, misleading-source resistance, deterministic replay where expected, and domain-specific correctness.

At least one independent evaluator should reproduce the benchmark from a clean checkout and review limitations and failure modes.

## Evidence package

For each gate retain:
- exact commit/version;
- target environment/runtime digest;
- configuration fingerprint with secrets removed;
- command/protocol;
- timestamp;
- raw result artifact;
- pass/fail decision;
- failures and residual risks;
- remediation;
- required independent sign-off.

Only after these artifacts exist may an external gate change from external_required to verified_external.
