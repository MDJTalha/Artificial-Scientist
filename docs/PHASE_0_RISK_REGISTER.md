# Phase 0 — Scientific Risk Register and Evaluation Baseline

**Status:** Repository-complete baseline for Phase 0. This defines the risk taxonomy, scoring method, acceptance evidence, and evaluation protocol. It does not claim operational or scientific risks have already been eliminated.

## 1. Risk taxonomy

| ID | Risk | Impact | Likelihood | Initial rating | Required control |
|---|---|---:|---:|---:|---|
| R0-01 | Unsupported or fabricated scientific claim | 5 | 3 | 15 | Provenance, citation validation, independent verification, claim/evidence linkage |
| R0-02 | Confirmation bias / failure to test alternatives | 5 | 3 | 15 | Competing hypotheses, falsification criteria, discriminating tests |
| R0-03 | Non-reproducible computation | 4 | 3 | 12 | Immutable inputs/configuration, dependency/runtime manifest, digests, replay |
| R0-04 | Prompt/document injection changes scientific permissions | 5 | 3 | 15 | Treat research content as untrusted; authorization outside model-controlled text |
| R0-05 | Generated computation escapes execution boundary | 5 | 3 | 15 | Fail-closed Phase 6 adapter; reviewed OS sandbox required before untrusted execution |
| R0-06 | Cross-tenant data disclosure | 5 | 2 | 10 | Principal/tenant authorization, object scoping, negative tests, audit |
| R0-07 | Scientific memory silently rewrites history | 4 | 2 | 8 | Immutable versions, contradiction records, rollback-as-new-version |
| R0-08 | Autonomous external side effect | 5 | 2 | 10 | Explicit approval gates and hard physical-action/publication boundaries |
| R0-09 | Benchmark contamination or self-scoring | 4 | 3 | 12 | Versioned cases, independent verification, governance blocking |
| R0-10 | Dependency or deployment compromise | 5 | 2 | 10 | Pinned environments, provenance, vulnerability review, independent security review |
| R0-11 | Resource exhaustion | 4 | 3 | 12 | Bounded requests, quotas, timeouts, concurrency controls, cleanup |
| R0-12 | Sensitive data/credential leakage | 5 | 2 | 10 | Secret exclusion, bounded audit metadata, artifact controls, least privilege |

## 2. Scoring

Impact and likelihood are each scored from 1 (low) to 5 (severe/high). Risk score = impact × likelihood.

- 1–4: monitor and test.
- 5–9: mitigation required before material scope expansion.
- 10–15: release-gating control required.
- 16–25: block the affected capability until independently reviewed.

Residual risk must never be represented as zero merely because a unit test passes.

## 3. Evaluation baseline

Every material capability is evaluated against four evidence classes:

1. Correctness: deterministic reference cases and negative cases.
2. Scientific integrity: provenance, falsification, uncertainty, contradiction and misleading-source cases.
3. Security: authorization, isolation, resource-abuse, secret-disclosure and fail-closed cases.
4. Reproducibility: repeat execution, exact inputs/configuration, environment/dependency identity, output digests.

Each evaluation record must contain the commit/version, test command, dataset/case version, observed result, failures, limitations, and reviewer/owner.

## 4. Release rule

A capability is not considered complete merely because implementation exists. It is complete only when its repository exit criteria are covered by tests and its deployment/scientific external gates have concrete evidence and sign-off where the gate is explicitly external.

Phase 0 establishes the acceptance contract used by Phases 1–14 and prevents invented benchmark numbers or unsupported production claims.
