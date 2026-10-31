# Phase 0 — Evaluation Protocol

## Purpose

Provide a repeatable baseline for evaluating ASDS without inventing scientific performance numbers.

## Required case classes

- Evidence: supported claim, unsupported claim, contradictory sources, unavailable source.
- Hypothesis: two competing explanations, incomplete assumptions, non-falsifiable candidate.
- Computation: known reference result, tolerance boundary, non-finite input, resource-bound input.
- Security: unauthorized tenant, revoked membership, cross-tenant object identifier, injected instruction, secret-bearing input.
- Reproducibility: same immutable configuration twice; changed dependency/configuration; interrupted execution and recovery.
- Governance: missing benchmark, critical failure, conditional non-critical failure, complete passing suite.
- Autonomy boundary: missing approval, expired/revoked authorization, physical-action request, publication/submission request.

## Required reporting fields

case_id, case_version, commit_sha, component, input_digest, expected_outcome, observed_outcome, passed, failure_class, limitations, timestamp, and reviewer/owner.

## Scientific interpretation

The baseline is an evaluation harness specification, not a performance claim. Scores must be produced from actual executions against versioned cases. If a case cannot be reproduced, the evaluation is incomplete rather than automatically passing.
