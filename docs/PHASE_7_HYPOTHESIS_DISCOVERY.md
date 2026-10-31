# Phase 7 — Hypothesis Discovery and Falsification

## Implemented scope

The decomposition endpoint extracts only conservative patterns from the research question, reports unresolved variables/context/controls/time horizon, and returns clarification prompts. It labels its method as a bounded heuristic and leaves unrecognized variables unset rather than inventing them.

The Phase 7 API exposes `POST /api/v1/discovery/decompose`, `POST /api/v1/discovery/generate`, `POST /api/v1/discovery/assess`, and `POST /api/v1/discovery/prior-work-screen`. Assessment accepts one research question and 2–10 competing, caller-supplied candidates. Prior-work screening queries the existing OpenAlex and Crossref metadata connectors for 2–5 candidates, without persisting search results. Each candidate must include assumptions, alternative explanations, predictions, falsification criteria, and a discriminating test. Source and claim references are validated against stored records before any hypothesis is written.

The bounded generation endpoint produces a small positive/inverse/null hypothesis set from explicitly supplied variables. It is deterministic, evidence-free, marked `requires_human_review`, and does not persist records or claim novelty, truth, or causality.

The service:
- checks required structure and bounded input sizes with Pydantic;
- runs a bounded metadata-only prior-work search against OpenAlex/Crossref and returns source titles, DOI/year, provider status, and an explicit non-novelty-guarantee interpretation;
- computes a transparent 0–100 **completeness** score from six explicit rubric checks;
- flags likely near-duplicate statements using a deterministic lexical similarity heuristic;
- records predictions and discriminating tests in immutable `HypothesisRecord` records;
- stores provenance, linked source/claim IDs, assumptions, alternatives, falsification criteria, and a provisional novelty-screen status;
- emits the existing append-only record-creation audit events;
- returns record IDs and explicit limitations.

## API request example

Use `POST /api/v1/discovery/decompose` first when useful. Supply `research_question` and optional `domain_context`; the response includes candidate independent/dependent variables, question type, missing elements, and clarification prompts. Treat all extracted values as editable suggestions.

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

## Prior-work screening

Call `POST /api/v1/discovery/prior-work-screen` with a research question, 2–5 candidate titles/statements, optional provider selection, and `results_per_candidate` from 1 to 5. The route reuses the existing fixed-endpoint OpenAlex/Crossref adapters with persistence disabled. It returns per-candidate query status, matched metadata, provider status, and interpretation. An unavailable provider is reported rather than silently treated as an empty result set.

The screen is a discovery aid, not an exhaustive systematic review. It does not fetch full text or determine whether a paper genuinely anticipates a hypothesis. Relevant-looking titles require manual source inspection and comparison of methods, results, assumptions, and limitations. No matches means only that the selected providers returned no match for that query.

## Rubric and interpretation

Six equally weighted checks contribute to completeness: explicit assumptions, alternative explanations, testable predictions, falsification criteria, a discriminating test, and traceable source/claim links. The score is a structural checklist only. It is not a confidence estimate, ranking of truth, or substitute for expert judgment.

## Explicit limitations and remaining acceptance gates

- Generated suggestions are deterministic directional/null templates, not model-derived scientific discoveries. They remain review-required and evidence-free.
- Novelty assessment is provisional. The endpoint does not itself run a literature search or guarantee that a hypothesis is novel.
- Lexical similarity can miss paraphrases and can flag unrelated wording; a human should review every duplicate warning.
- Candidate persistence uses one SQLite transaction for the whole batch; a validation or write failure rolls back every candidate and its audit event.
- Research-record, discovery, and knowledge-graph access is tenant-scoped in the integrated main branch. Protected routes require authenticated tenant membership outside development, and evidence references are resolved within the caller's tenant. Production exposure remains subject to the separate live OIDC, operational, and independent-security release gates.
- Scientific validity requires domain-expert review, a documented literature-search protocol, and subsequent Phase 8 experiment planning and Phase 9 independent analysis.

## CI acceptance

Phase 7 code acceptance requires the latest branch SHA to pass frontend type-check/tests/build, Ruff, and the complete backend test suite on Python 3.12 and 3.13. A historical green run does not validate later commits. No PR is merged automatically.


## Operational guardrails added during implementation

Discovery POST requests are capped at 1 MiB before JSON parsing. The guard enforces both declared `Content-Length` and streamed body size, so chunked requests cannot bypass the limit. Requests above the limit receive HTTP 413 and are not passed to Pydantic or route handlers. Regression coverage verifies rejection of an oversized body.

This limit is a resource-abuse guard, not authentication, rate limiting, or a substitute for an upstream proxy/server request limit. Deployments should also configure reverse-proxy body limits, connection/timeouts, per-principal rate limits, and monitoring. Tenant-scoped authorization and cross-tenant negative tests are implemented for the integrated research-record/discovery paths. Do not treat repository tests as a substitute for live deployment validation or independent security review.


## Bounded hypothesis generation

The integrated discovery service also exposes `POST /api/v1/discovery/generate`. It accepts an explicitly structured independent variable, dependent variable, system/population, and optional context, then produces a small deterministic set of directional and null candidates. Every generated candidate is marked `requires_human_review` and contains assumptions, alternatives, predictions, falsification criteria, and a discriminating test.

This is intentionally **bounded hypothesis synthesis**, not autonomous scientific discovery. It does not invent evidence, retrieve literature, estimate truth probabilities, claim novelty, or execute experiments. Generated candidates must pass the normal assessment, prior-work screening, Phase 8 planning, and Phase 9 independent-verification controls before they can influence a research conclusion.
