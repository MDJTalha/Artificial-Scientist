# Phase 7 — Hypothesis Discovery and Falsification

## Implemented scope

The Phase 7 API is exposed at `POST /api/v1/discovery/assess`. It accepts one research question and 2–10 competing, caller-supplied candidates. Each candidate must include assumptions, alternative explanations, predictions, falsification criteria, and a discriminating test. Source and claim references are validated against stored records before any hypothesis is written.

The service:
- checks required structure and bounded input sizes with Pydantic;
- computes a transparent 0–100 **completeness** score from six explicit rubric checks;
- flags likely near-duplicate statements using a deterministic lexical similarity heuristic;
- records predictions and discriminating tests in immutable `HypothesisRecord` records;
- stores provenance, linked source/claim IDs, assumptions, alternatives, falsification criteria, and a provisional novelty-screen status;
- emits the existing append-only record-creation audit events;
- returns record IDs and explicit limitations.

## API request example

```json
{
  "research_question": "How does temperature affect reaction rate under fixed pressure?",
  "novelty_screen_status": "not_run",
  "candidates": [
    {
      "title": "Temperature increases rate",
      "statement": "Increasing temperature increases reaction rate under fixed pressure.",
      "assumptions": ["Pressure remains fixed."],
      "alternative_explanations": ["Catalyst concentration changed."],
      "predictions": ["Measured rate increases in the predefined range."],
      "falsification_criteria": ["The rate does not increase beyond measurement uncertainty."],
      "discriminating_test": "Randomize temperature levels and measure rate with blinded analysis.",
      "source_record_ids": [],
      "claim_record_ids": []
    },
    {
      "title": "Temperature decreases rate",
      "statement": "Increasing temperature decreases reaction rate under fixed pressure.",
      "assumptions": ["Pressure remains fixed."],
      "alternative_explanations": ["A competing reaction dominates."],
      "predictions": ["Measured rate decreases in the predefined range."],
      "falsification_criteria": ["The rate does not decrease beyond measurement uncertainty."],
      "discriminating_test": "Randomize temperature levels and measure rate with blinded analysis.",
      "source_record_ids": [],
      "claim_record_ids": []
    }
  ]
}
```

A successful request returns `201 Created`, per-candidate rubric results, near-duplicate warnings, and the persisted hypothesis record IDs. Source and claim IDs, when provided, must point to records of the correct type. If the request is marked `screened`, include `novelty_screen_notes`; this is caller-declared metadata and not proof that the search was adequate.

## Rubric and interpretation

Six equally weighted checks contribute to completeness: explicit assumptions, alternative explanations, testable predictions, falsification criteria, a discriminating test, and traceable source/claim links. The score is a structural checklist only. It is not a confidence estimate, ranking of truth, or substitute for expert judgment.

## Explicit limitations and remaining acceptance gates

- Candidate hypotheses are supplied by a caller. No model-driven hypothesis generation is claimed.
- Novelty assessment is provisional. The endpoint does not itself run a literature search or guarantee that a hypothesis is novel.
- Lexical similarity can miss paraphrases and can flag unrelated wording; a human should review every duplicate warning.
- Record writes use the existing append-only record store, but this endpoint does not provide a cross-record database transaction. A storage failure during a multi-candidate write could leave a subset persisted; inspect the returned error and record list before retrying.
- The existing research-record API is not tenant-scoped. Do not expose Phase 7 or the general records API to untrusted multi-tenant traffic until the Phase 6 identity and authorization release gates are independently satisfied.
- Scientific validity requires domain-expert review, a documented literature-search protocol, and subsequent Phase 8 experiment planning and Phase 9 independent analysis.

## CI acceptance

Phase 7 code acceptance requires the latest branch SHA to pass frontend type-check/tests/build, Ruff, and the complete backend test suite on Python 3.12 and 3.13. A historical green run does not validate later commits. No PR is merged automatically.
