# Phase 6 — Controlled Computational Laboratory

**Status: implementation in progress; phase is not complete.**  
**Branch:** `phase-6-controlled-lab`, targeting `main`.

## Scope delivered in this slice

The first lab API is a declarative runner over existing allowlisted math tools. It does not accept or execute Python source code.

- `POST /api/v1/lab/runs` accepts a titled run with 1–20 declarative steps and persists the result in SQLite.
- `GET /api/v1/lab/runs` lists stored runs with bounded pagination; `GET /api/v1/lab/runs/{run_id}` retrieves one run. `GET /api/v1/lab/runs/{run_id}/artifacts` lists artifact metadata, and `GET /api/v1/lab/artifacts/{artifact_id}` retrieves an artifact after digest and provenance checks. Stored run records are checked against a canonical digest covering all persisted response fields except the digest itself. Each successful run is atomically stored with a JSON result artifact and provenance metadata.
- Allowed operations are `symbolic`, `integrate`, `root`, `statistics`, and `unit_convert`.
- Every step is validated using the same Pydantic contracts as the existing math endpoints.
- Duplicate step IDs, unknown operations, extra fields in typed math requests, non-finite JSON values, oversized step inputs, and oversized run configurations are rejected. An ASGI middleware also rejects lab-run request bodies over 64 KiB with HTTP 413 before JSON parsing, including requests without a trustworthy `Content-Length` header.
- A failed step stops subsequent work; later steps are explicitly marked skipped.
- Each response contains a run ID, UTC timestamps, per-step duration/status, bounded diagnostic logs, SHA-256 hashes of canonicalized configuration and the complete run record, and optional plan/seed metadata.
- The runner does not expose filesystem, network, shell, import, or arbitrary-code capabilities to expressions.

## Example request

```json
{
  "title": "Reference integral",
  "steps": [
    {
      "step_id": "integral",
      "operation": "integrate",
      "inputs": {
        "expression": "x**2",
        "variable": "x",
        "lower": 0,
        "upper": 1
      }
    }
  ],
  "random_seed": 7
}
```

The configuration and result hashes support integrity comparison; the result digest covers the full persisted response record, including title, timestamps, durations, steps, logs, and metadata. These hashes are not digital signatures, do not protect against an attacker who can rewrite both the record and its digest, and do not prove scientific validity.

## Current limitations — do not treat Phase 6 as complete

- Canonical JSON run-result artifacts are persisted as SQLite BLOBs with SHA-256 verification and provenance links to the run, configuration digest, result digest, optional plan ID, and step IDs. General binary attachments are also stored in a separate SQLite table, limited to 10 MiB each, 100 attachments per run, and 50 MiB total binary storage per run, with filename/media-type validation, SHA-256 checks, run/plan provenance, bounded streamed upload, and authenticated metadata/download endpoints. Identical uploads are idempotent and do not consume quota twice. An internal, explicitly invoked, bounded retention purge deletes expired runs and cascades their artifacts while preserving tombstones. An opt-in job entry point is available via `python -m artificial_scientist.lab.retention`; it requires `ARTIFICIAL_SCIENTIST_LAB_RETENTION_DAYS` and is intended to be invoked by an operator-managed scheduler. No scheduler is installed or started by the API. Complete cross-system lifecycle management, object-store support, and per-user quotas remain unimplemented. The current quotas are per-run limits, not per-user or tenant-level quotas. A ZIP export endpoint packages the run record, verified JSON result artifacts, binary attachment bytes, binary metadata, and a SHA-256 manifest; the manifest is not digitally signed.
- Each allowlisted lab step runs in a separate spawned child process with a configurable hard wall-clock deadline (default 10 seconds, maximum 30 seconds). Cleanup requests termination, waits briefly, then escalates to a hard kill if the worker remains alive; regression tests cover the escalation path. On POSIX systems, the worker applies RLIMIT_CPU (25 seconds), RLIMIT_AS (2 GiB address space), RLIMIT_FSIZE (8 MiB per file), RLIMIT_NOFILE (64 descriptors), and RLIMIT_CORE (0 where available). These are kernel-enforced process resource limits, but not a complete sandbox: filesystem access, network access, syscalls, and kernel attack surface are not isolated. Windows lacks these standard-library POSIX limits.
- The lab router requires `X-Lab-API-Key` when `ARTIFICIAL_SCIENTIST_ENV` is not `development`. If `ARTIFICIAL_SCIENTIST_ENV` is unset, the application defaults to `production`, and the lab API fails closed with HTTP 503 until authentication is configured. For local development only, explicitly set `ARTIFICIAL_SCIENTIST_ENV=development`; this bypass is unauthenticated and must never be exposed to untrusted traffic. Configure `ARTIFICIAL_SCIENTIST_LAB_API_KEY` with a high-entropy secret of at least 32 characters; non-development environments fail closed with HTTP 503 if the key is missing or shorter than 32 characters and reject missing/incorrect presented keys with HTTP 401. This is a shared-key gate, not per-user identity, role-based authorization, rate limiting, or a substitute for TLS and network controls. Rotate the key through the deployment secret manager; never commit it to source control.
- This is not a complete operating-system sandbox. Authentication and POSIX rlimits do not make arbitrary code safe; keep arbitrary generated code disabled and keep the service on trusted infrastructure until filesystem/network isolation and the complete execution boundary are independently reviewed.
- A seed is recorded as metadata only; these deterministic math operations do not currently consume it.
- Runs persist their original validated configuration and a runtime manifest (Python implementation/version, platform, machine, and key scientific dependency versions). `POST /api/v1/lab/runs/{run_id}/verify` replays that configuration and compares configuration digest, exact environment manifest, and per-step outputs. Verification is an observed replay comparison, not proof of scientific validity or bit-for-bit reproducibility across platforms. Older records without replayable configuration return HTTP 409. Each API-created run now has a durable execution-attempt record created before computation; process startup reconciles stale running attempts to either their already-persisted terminal run state or an explicit interrupted state. `GET /api/v1/lab/runs/{run_id}/execution-status` exposes safe status metadata. Retention preserves attempt hashes/status while redacting stored request configuration. Cross-system durable audit linkage remains future acceptance work.
- The lab currently stops at the first failed step and does not support arbitrary dependency graphs or parallel execution.

## Retention job

Retention is deliberately **opt-in** to avoid accidental data deletion.

1. Set `ARTIFICIAL_SCIENTIST_DB_PATH` to the same SQLite database used by the deployment.
2. Set `ARTIFICIAL_SCIENTIST_LAB_RETENTION_DAYS` to an explicit integer from 1 through 36500.
3. From the installed backend environment, run `python -m artificial_scientist.lab.retention` from a deployment scheduler or controlled operator job.
4. Restrict database access and review the retention policy before enabling it. Each purged run leaves a tombstone with its run ID, configuration/result digests, cutoff, deletion time, reason, and number of deleted artifacts.

The entry point does not create a background thread or automatically schedule itself. Test it against a disposable database before using a production database.

## Acceptance criteria for full Phase 6

- [x] Strict declarative input schema and finite configuration size.
- [x] Explicit allowlist of supported operation types; no arbitrary code execution.
- [x] Bounded step count, bounded step input size, and an ASGI-level 64 KiB request-body cap tested both with an oversized declared body and streamed chunks without `Content-Length`.
- [x] Per-step status, logs, duration measurement, and configuration/result SHA-256 digests.
- [x] Fail-fast behavior with later steps marked skipped.
- [x] API and adversarial-input tests added.
- [ ] CI passes on the final Phase 6 head (must be checked from a fresh GitHub Actions run).
- [x] Durable execution-attempt records are created before API execution; startup recovery marks stale attempts interrupted or reconciles them to a persisted run; status API and regression tests are included.
- [x] Durable SQLite run storage, bounded listing/retrieval, and full-record integrity checks.
- [x] Durable JSON result artifacts with byte-digest verification and run/plan/step provenance metadata.
- [x] ZIP export package containing the run record, verified result artifacts, and a SHA-256 manifest, with regression coverage. The manifest is not digitally signed.
- [x] General binary artifact upload/download and digest/provenance checks, with a 10 MiB limit and regression coverage. Per-run quotas are enforced (100 attachments / 50 MiB). Optional ClamAV TCP INSTREAM scanning is integrated; non-development uploads fail closed unless a scanner is configured and reports clean. The scanner outcome and timestamp are persisted in attachment provenance and included in metadata/exports; legacy attachments without a scan record remain readable. Production still requires an operated ClamAV service and deployment verification. Cross-system plan/record linkage, object-store support, and per-user/tenant quotas remain outstanding. Retention redacts stored execution request payloads while preserving digest-backed attempt metadata.
- [x] Opt-in retention job entry point with bounded batches, validation, tombstone preservation, and regression tests.
- [ ] Deployment scheduler configuration and operational verification of retention against the target database.
- [x] Enforced per-step wall-clock timeout, termination-to-kill escalation, and regression tests for timeout handling and cleanup escalation.
- [x] POSIX worker CPU/address-space/file-size/open-descriptor limits are applied and their configuration is regression-tested. These limits are not filesystem/network isolation.
- [ ] Complete OS-level sandbox with filesystem/network isolation and independent security review.
- [x] Runtime environment manifest and stored-configuration rerun/verification endpoint with output comparison tests.
- [x] Shared API-key gate for lab endpoints outside development, with unauthorized and missing-secret tests; this is not per-user authorization.
- [ ] Security review of the execution boundary before enabling generated code or untrusted users.

Phase 6 remains in progress until all required security, durability, reproducibility, and CI gates are evidenced. No arbitrary generated code should be enabled before a separately reviewed isolation boundary exists.


## Binary attachment malware scanning

The upload API uses ClamAV's TCP INSTREAM protocol when `ARTIFICIAL_SCIENTIST_CLAMAV_HOST` is configured. The outcome (`clean`, `skipped_development`, or `not_scanned` for direct store-level inserts), scanner identity when applicable, and timestamp are persisted with attachment provenance so listings and exports retain the evidence. Optional settings are `ARTIFICIAL_SCIENTIST_CLAMAV_PORT` (default `3310`) and `ARTIFICIAL_SCIENTIST_CLAMAV_TIMEOUT_SECONDS` (default `5`, allowed range 0.1–30 seconds). A clean result is required before storing an attachment. An infection returns HTTP 422; a missing or unhealthy scanner returns HTTP 503 and the attachment is not stored. In development only, if no scanner host is configured, uploads are allowed with response field `scan_status: skipped_development`; configured scanners are still used in development.

Deployments must run and maintain a supported ClamAV service, restrict access to its TCP endpoint, keep signatures updated, and verify the production configuration. The integration does not replace file-format validation, per-tenant quotas, object-store isolation, or security review.
