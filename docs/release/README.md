# Release evidence

This directory contains machine-readable release-gate policy and validation rules.

The policy deliberately separates **repository evidence** from **external certification evidence**. CI, unit tests, mocks, or documentation must never be treated as proof of production deployment, live identity-provider validation, OS sandbox certification, independent security review, or scientific validity.

When an external gate is completed, attach concrete evidence with the target/version, commands or protocol, outcome, limitations, risks, and independent sign-off. Do not change a gate to `complete` merely because repository tests pass.
