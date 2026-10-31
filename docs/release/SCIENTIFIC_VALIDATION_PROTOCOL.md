# Scientific Validation Protocol

This protocol defines a reproducible evaluation package. Passing the repository smoke benchmark does not establish scientific validity.

## Benchmark requirements

Pin:
- source commit and dependency lock state;
- benchmark dataset version and checksums;
- random seeds where applicable;
- expected outputs and numerical tolerances;
- execution environment;
- evaluator version.

## Evaluation dimensions

1. numerical and symbolic correctness;
2. unit and dimensional correctness;
3. reproducibility across repeated runs;
4. provenance and evidence preservation;
5. resistance to unsupported claims;
6. resistance to prompt injection and misleading source material;
7. deterministic replay where expected;
8. domain-specific correctness;
9. failure-mode reporting and uncertainty handling.

## Independent reproduction

A separate evaluator should clone a clean checkout, install the pinned environment, run the benchmark without implementation guidance, compare raw outputs with the published expected results, and document deviations.

Retain raw machine-readable results and a signed domain-expert assessment. Do not label a benchmark pass as a scientific certification.
