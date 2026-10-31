# Phase 0 — Scientific Risk Register and Evaluation Baseline

**Status:** Repository-side baseline completed; operational and scientific evidence remains execution-gated.

This register turns the project charter into explicit, testable risk controls. It does not certify the deployment or the scientific claims.

## Risk register

| ID | Risk | Impact | Likelihood | Control | Evidence required |
|---|---|---|---|---|---|
| R0-01 | Untrusted generated code reaches the service host | Critical | Medium | Fail-closed execution adapter; arbitrary execution disabled outside explicit development mode | Reviewed OS sandbox deployment + adversarial tests |
| R0-02 | Cross-tenant research data disclosure | Critical | Medium | Tenant-scoped stores, membership authorization, negative tests, opaque IDs | Independent security review + deployment validation |
| R0-03 | Invalid identity token accepted | Critical | Medium | OIDC issuer/audience/JWKS validation, RS256 restriction, claim/time validation | Live provider validation and key-rotation evidence |
| R0-04 | Scientific result is accepted without independent checking | High | Medium | Independent verifier, replay, digest/provenance checks, governance gates | Benchmark and replication evidence |
| R0-05 | Literature novelty is overstated | High | High | Prior-work screening is explicitly provisional; duplicate heuristic is review aid only | Documented literature search + expert review |
| R0-06 | Audit/provenance history is altered or incomplete | High | Low/Medium | Immutable record model, digests, append-only audit controls, export manifests | Recovery rehearsal + independent review |
| R0-07 | Resource exhaustion impacts service or tenant | High | Medium | Bounded requests, step limits, process limits, quotas, timeouts | Adversarial load/resource testing |
| R0-08 | Recovery restores inconsistent ownership/data | High | Medium | Transactional migration/legacy-claim workflow and tenant-scoped persistence | Sanitized backup/restore/rollback rehearsal |
| R0-09 | Physical-world action occurs without explicit authorization | Critical | Low | Hard rejection of physical-action domains; no physical actuator interface | Independent safety review |
| R0-10 | Model/source prompt injection corrupts research decisions | High | Medium | Evidence/provenance boundaries and non-claiming discovery semantics | Adversarial scientific-integrity evaluation |
| R0-11 | Documentation overstates implementation maturity | Medium | Medium | Current-status evidence rules; CI and release-gate documentation | Release audit |
| R0-12 | Dependency or build compromise affects reproducibility | High | Medium | Lock/configuration evidence, CI, runtime manifests | Dependency inventory, provenance and vulnerability review |

## Evaluation baseline

The minimum scientific evaluation package before a production-facing claim is:

1. **Correctness:** deterministic reference cases for every scientific tool and verification primitive.
2. **Reproducibility:** replay from recorded configuration, code/version and environment manifest.
3. **Falsification:** every accepted hypothesis includes explicit falsification criteria and a discriminating test.
4. **Evidence integrity:** claims and hypotheses remain linked to source/evidence records.
5. **Negative testing:** cross-tenant access, malformed identity, unauthorized approval, resource exhaustion and forbidden physical-action paths fail safely.
6. **Robustness:** misleading-source, prompt-injection and contradictory-evidence cases are evaluated.
7. **Independent replication:** representative findings are reproduced by an independent process or reviewer.
8. **Expert review:** domain-qualified reviewers assess validity, novelty interpretation and limitations.
9. **Governance:** benchmark failures or critical security/integrity findings block release.

## Release interpretation

Passing repository tests establishes **implementation evidence**, not scientific truth or production certification. Each external gate must record scope, software commit/version, environment, commands, outcome, failures, limitations, dependencies/data constraints, security/scientific-integrity risks, and reviewer/sign-off information.

## Current unresolved gates

- Reviewed OS-level execution sandbox.
- Live OIDC/JWKS provider and rotation validation.
- Sanitized production migration/backup/restore/rollback rehearsal.
- Independent security review.
- Operational deployment validation.
- Scientific benchmark, replication, domain-expert and adversarial-integrity evaluation.
