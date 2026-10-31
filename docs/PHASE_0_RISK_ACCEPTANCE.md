# Phase 0 — Risk Acceptance and Incident Decision Record

## Decision classes

- BLOCK: a critical security, integrity, authorization, or safety invariant is violated.
- CONDITIONAL: the capability may remain available only within explicitly bounded scope with named residual risks.
- RELEASE: required repository tests and applicable external evidence are complete.

## Mandatory incident response

For a material failure: stop the affected workflow, preserve evidence without secrets, mark affected findings unreliable, identify affected records/artifacts, correct or retract conclusions where appropriate, add a regression test, and record the preventive decision.

No incident record may be closed solely because the software was redeployed.
