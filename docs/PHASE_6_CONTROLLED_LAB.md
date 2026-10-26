# Phase 6 — Controlled Computational Laboratory

**Status: initial implementation slice; phase is not complete.**  
**Branch:** `phase-6-controlled-lab`, stacked on `phase-5-mathematical-tools`.

## Scope delivered in this slice

The first lab API is a declarative runner over existing allowlisted math tools. It does not accept or execute Python source code.

- `POST /api/v1/lab/runs` accepts a titled run with 1–20 declarative steps.
- Allowed operations are `symbolic`, `integrate`, `root`, `statistics`, and `unit_convert`.
- Every step is validated using the same Pydantic contracts as the existing math endpoints.
- Duplicate step IDs, unknown operations, extra fields in typed math requests, non-finite JSON values, oversized step inputs, and oversized run configurations are rejected.
- A failed step stops subsequent work; later steps are explicitly marked skipped.
- Each response contains a run ID, UTC timestamps, per-step duration/status, bounded diagnostic logs, SHA-256 hashes of canonicalized configuration and result payloads, and optional plan/seed metadata.
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

The configuration and result hashes support integrity comparison; they are not digital signatures and do not prove that a result is scientifically valid.

## Current limitations — do not treat Phase 6 as complete

- Runs and artifacts are returned in the HTTP response but are **not yet durably persisted** by this lab API.
- Duration is measured, but no hard process-level wall-clock timeout or OS-level CPU/memory quota is enforced.
- This is not an operating-system sandbox. The endpoint must remain on trusted local infrastructure; the application currently has no authentication.
- A seed is recorded as metadata only; these deterministic math operations do not currently consume it.
- Artifact storage, environment/dependency manifests, replay across versions, interruption recovery, and durable audit linkage remain future acceptance work.
- The lab currently stops at the first failed step and does not support arbitrary dependency graphs or parallel execution.

## Acceptance criteria for full Phase 6

- [x] Strict declarative input schema and finite configuration size.
- [x] Explicit allowlist of supported operation types; no arbitrary code execution.
- [x] Bounded step count and bounded step input size.
- [x] Per-step status, logs, duration measurement, and configuration/result SHA-256 digests.
- [x] Fail-fast behavior with later steps marked skipped.
- [x] API and adversarial-input tests added.
- [ ] CI passes on the final Phase 6 head (must be checked from a fresh GitHub Actions run).
- [x] Durable SQLite run storage, bounded listing/retrieval, and result-payload integrity checks.\n- [ ] Durable artifact blob storage and full provenance linkage to experiment plans/records.
- [ ] Enforced timeout and process/resource isolation tests.
- [ ] Reproducible environment manifest and rerun/verification workflow.
- [ ] Security review of the execution boundary before enabling generated code or untrusted users.

Phase 6 remains in progress until all required security, durability, reproducibility, and CI gates are evidenced. No arbitrary generated code should be enabled before a separately reviewed isolation boundary exists.
