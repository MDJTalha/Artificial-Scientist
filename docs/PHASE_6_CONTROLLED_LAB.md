# Phase 6 — Controlled Computational Laboratory

**Status: initial implementation slice; phase is not complete.**  
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

- Canonical JSON run-result artifacts are persisted as SQLite BLOBs with SHA-256 verification and provenance links to the run, configuration digest, result digest, optional plan ID, and step IDs. An internal, explicitly invoked, bounded retention purge now deletes expired runs and cascades their artifacts while preserving a tombstone with both digests, cutoff, reason, deletion time, and artifact count. It is not exposed through the unauthenticated API and is not automatically scheduled. General binary scientific attachments, export packages, retention scheduling, and complete cross-system lifecycle management remain unimplemented.
- Each allowlisted lab step now runs in a separate spawned child process with a configurable hard wall-clock deadline (default 10 seconds, maximum 30 seconds). Cleanup requests termination, waits briefly, then escalates to a hard kill if the worker remains alive; regression tests cover the escalation path. This is process separation, not an OS security sandbox, and no OS-level CPU/memory quota is enforced.
- The lab router now requires `X-Lab-API-Key` when `ARTIFICIAL_SCIENTIST_ENV` is not `development`. Configure `ARTIFICIAL_SCIENTIST_LAB_API_KEY` with a high-entropy secret of at least 32 characters; non-development environments fail closed with HTTP 503 if the key is missing or shorter than 32 characters and reject missing/incorrect presented keys with HTTP 401. Local development remains unauthenticated by design. This is a shared-key gate, not per-user identity, role-based authorization, rate limiting, or a substitute for TLS and network controls. Rotate the key through the deployment secret manager; never commit it to source control.
- This is not an operating-system sandbox. Authentication does not make execution safe for untrusted workloads; keep the service on trusted infrastructure until OS-level isolation and resource quotas are independently reviewed.
- A seed is recorded as metadata only; these deterministic math operations do not currently consume it.
- Runs now persist their original validated configuration and a runtime manifest (Python implementation/version, platform, machine, and key scientific dependency versions). `POST /api/v1/lab/runs/{run_id}/verify` replays that configuration and compares configuration digest, exact environment manifest, and per-step outputs. Verification is an observed replay comparison, not proof of scientific validity or bit-for-bit reproducibility across platforms. Older records without replayable configuration return HTTP 409. Interruption recovery and cross-system durable audit linkage remain future acceptance work.
- The lab currently stops at the first failed step and does not support arbitrary dependency graphs or parallel execution.

## Acceptance criteria for full Phase 6

- [x] Strict declarative input schema and finite configuration size.
- [x] Explicit allowlist of supported operation types; no arbitrary code execution.
- [x] Bounded step count, bounded step input size, and an ASGI-level 64 KiB request-body cap tested both with an oversized declared body and streamed chunks without `Content-Length`.
- [x] Per-step status, logs, duration measurement, and configuration/result SHA-256 digests.
- [x] Fail-fast behavior with later steps marked skipped.
- [x] API and adversarial-input tests added.
- [ ] CI passes on the final Phase 6 head (must be checked from a fresh GitHub Actions run).
- [x] Durable SQLite run storage, bounded listing/retrieval, and full-record integrity checks.
- [x] Durable JSON result artifacts with byte-digest verification and run/plan/step provenance metadata.
- [ ] General binary artifact support, automated retention scheduling, export packages, and complete provenance linkage to experiment plans/records. The bounded internal purge primitive and audit tombstones are implemented, but no public deletion API or scheduler is enabled.
- [x] Enforced per-step wall-clock timeout, termination-to-kill escalation, and regression tests for both timeout handling and cleanup escalation.
- [ ] OS-level process/resource isolation and CPU/memory quota tests.
- [x] Runtime environment manifest and stored-configuration rerun/verification endpoint with output comparison tests.
- [x] Shared API-key gate for lab endpoints outside development, with unauthorized and missing-secret tests; this is not per-user authorization.
- [ ] Security review of the execution boundary before enabling generated code or untrusted users.

Phase 6 remains in progress until all required security, durability, reproducibility, and CI gates are evidenced. No arbitrary generated code should be enabled before a separately reviewed isolation boundary exists.
