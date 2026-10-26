# Development Roadmap

The project is organized into **15 phases, Phase 0 through Phase 14**. These are capability stages, not delivery-date promises. Each phase must meet its exit criteria before the next stage expands scope materially. Safety and scientific integrity apply in every phase.

## Phase 0 — Charter and project definition

**Build:** mission, scientific constitution, scope, initial architecture, technology decisions, risk register, and acceptance strategy.  
**Exit criteria:** project goals and non-goals documented; system boundaries identified; initial threat model written; first research workflow and measures defined.  
**Current status:** foundational documentation started; formal risk register and evaluation baseline still need completion.

## Phase 1 — Core application foundation

**Build:** repository structure, backend skeleton, frontend skeleton, configuration, health endpoint, structured logging, type checking, linting, and test automation.  
**Exit criteria:** reproducible setup instructions; tests run locally; secrets excluded; CI checks are useful and truthful.

## Phase 2 — Research records and provenance

**Build:** typed data models for tasks, sources, claims, hypotheses, experiment plans/runs, artifacts, reviews, approvals, and audit events.  
**Exit criteria:** CRUD and relationship tests; provenance survives restarts; schema migrations/backup approach documented; no secrets in records.

## Phase 3 — Literature retrieval

**Build:** source connectors, metadata normalization, search, document ingestion, and citation validation.  
**Exit criteria:** source identifiers and retrieval metadata preserved; unavailable sources and rate limits handled; references verified against source records; licensing restrictions documented.

**Current implementation:** OpenAlex and Crossref metadata search adapters, bounded JSON handling, typed normalized results, DOI-based duplicate detection, SQLite source identity migration, provenance-carrying source records, and deterministic provider tests are implemented on `phase-3-literature-retrieval`. CI passed Ruff and 33 backend tests on Python 3.12 and 13. The frontend's type-check, 6 unit tests, and production build passed as well; see the [verified run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40264595989). The phase is ready for review, while integration remains sequential.

## Phase 4 — Knowledge and terminology

**Build:** structured scientific concepts, terminology, equation metadata, and supported relationships between concepts.  
**Exit criteria:** search and relationship tests pass; concept provenance is traceable; conflicting definitions are not silently merged.

**Current implementation:** typed concept and relation records, controlled vocabulary enums, concept/alias/definition search with server-side pagination, evidence-source links, directed relationships with explicit assertion status, self-link rejection, hierarchy-cycle checks, and bounded graph-neighborhood traversal are implemented on `phase-4-knowledge-graph`. The code commit passed Ruff and 46 backend tests on Python 3.12 and 13, plus frontend type-check, 6 tests, and production build; see the [verified run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40265564598) and `docs/PHASE_4_KNOWLEDGE_GRAPH.md`. Phase 4 is awaiting review/integration.

## Phase 5 — Mathematics and scientific tools

**Build:** symbolic computation, numerical calculations, units/dimensional checks where supported, statistics, and plotting.  
**Exit criteria:** reference cases and numerical tolerances documented; independent checks used where feasible; failures and unsupported operations are explicit.

**Current implementation:** bounded symbolic simplify/differentiate/integrate/solve/substitute/evaluate; bracketed real root finding; adaptive definite integration with error estimates; descriptive statistics; safe one-dimensional PNG plotting; and an allowlisted unit registry and dimensional-expression checker. The implementation uses a strict expression-AST allowlist rather than evaluating arbitrary Python text. The code commit passed Ruff, 75 backend tests on both Python 3.12 and 3.13, plus frontend type-check, 6 tests and production build; see the [verified CI run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40266731194) and `docs/PHASE_5_MATH_TOOLS.md`. Phase 5 implementation, documentation-head, and pull-request CI all passed; see the [code run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40266731194), [documentation-head push run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40266878173), and [pull-request run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40266895491). The phase is awaiting review/integration.

## Phase 6 — Controlled computational laboratory

**Build:** reproducible experiment configuration, managed dependencies, execution limits, logs, artifact capture, and an isolation strategy.  
**Exit criteria:** generated code cannot access unrestricted host resources; timeouts and resource limits tested; results can be traced to inputs and code. General agent-generated code is not enabled until the security boundary is reviewed.

### Phase 6 implementation status

**Current implementation:** `phase-6-controlled-lab` adds `POST /api/v1/lab/runs`, a bounded declarative runner for the existing symbolic, integration, root-finding, statistics, and unit-conversion operations. Typed inputs, 20-step and 64 KiB configuration limits, fail-fast behavior, per-step status/duration, and canonical configuration/result digests are implemented. It does not execute arbitrary Python. Run records and canonical JSON result artifacts are stored atomically in SQLite. Artifact APIs expose metadata and verified content; byte digests and provenance are checked against the canonical run record. Per-step wall-clock deadlines now run allowlisted operations in killable child processes. Each run persists its validated configuration and a runtime manifest of Python, platform, and key scientific dependency versions; `POST /api/v1/lab/runs/{run_id}/verify` replays the configuration and compares the configuration digest, runtime manifest, and per-step outputs. Backward-compatible integrity validation preserves retrieval of older records that predate these fields. Fresh GitHub Actions CI passed on commit `498b209a5fc8d5aa22bc82e5751081c1fa780639` for Python 3.12, Python 3.13, and frontend checks; see the [verified run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40276928135). The API enforces a 64 KiB lab-run request body limit, including streamed requests without `Content-Length`; lab endpoints require a shared API key outside development; and worker cleanup escalates from termination to hard kill and closes stopped process handles. An opt-in retention job entry point now removes expired runs in bounded batches and preserves digest-backed tombstones; it is disabled unless ARTIFICIAL_SCIENTIST_LAB_RETENTION_DAYS is explicitly configured and must be invoked by an operator-managed scheduler. Binary scientific attachment upload/download now supports bounded (10 MiB per file, 100 files and 50 MiB total per run) SQLite storage with digest and provenance checks; identical uploads are idempotent and per-user/tenant quotas remain outstanding. Object-store support, content scanning, per-user quotas, actual deployment scheduler configuration, a complete OS sandbox with filesystem/network isolation, per-user authorization/rate limiting, cross-system audit linkage remain outstanding. Durable execution-attempt records are now created before computation; store initialization after restart reconciles attempts stale for at least 15 minutes to a terminal persisted run or an explicit interrupted state, leaving fresh attempts untouched to avoid multi-worker false positives; a status endpoint and regression tests are included. Retention redacts stored request configurations while preserving attempt digests/status. A ZIP export endpoint now packages run records and verified artifacts with a SHA-256 manifest; the manifest is not digitally signed. POSIX workers now apply and test kernel-enforced CPU, address-space, file-size, open-descriptor, and core-dump limits; these rlimits do not constitute a complete sandbox. Phase 6 is **in progress, not complete**. See `docs/PHASE_6_CONTROLLED_LAB.md`.

## Phase 7 — Hypothesis and discovery engine

**Build:** research-question decomposition, competing hypotheses, prior-work checks, novelty screening, and falsification plans.  
**Exit criteria:** each hypothesis records evidence, assumptions, alternatives, and a proposed discriminating test; novelty is expressed as a provisional assessment, never guaranteed by search alone.

## Phase 8 — Experimental planning and orchestration

**Build:** explicit stateful workflow, baselines, variables, controls, success/failure criteria, approvals, and stopping conditions.  
**Exit criteria:** workflow transitions are validated; interruptions and failures are recoverable; consequential actions pause for authorization.

## Phase 9 — Analysis and independent verification

**Build:** validation of data and calculations, uncertainty analysis, statistical checks, baseline comparison, alternative explanations, and replication support.  
**Exit criteria:** benchmark cases and negative tests pass at agreed thresholds; an experiment is not marked successful solely because an agent says it succeeded.

## Phase 10 — Scientific memory and controlled learning

**Build:** versioned research memory, contradiction handling, update evaluation, provenance, rollback, and retention policy.  
**Exit criteria:** every retained claim has a source/status; updates have validation records; rejected or retracted findings can be corrected without erasing history.

## Phase 11 — Multi-agent research collaboration

**Build:** bounded specialist roles, delegation, shared structured records, conflict resolution, and resource budgets.  
**Exit criteria:** agents have distinct responsibilities; duplicated work and shared failure modes are measured; consensus is not treated as evidence; single-agent baselines are retained.

## Phase 12 — Scientific writing

**Build:** evidence-linked reports/manuscripts, verified bibliographies, figures, methods, limitations, data/code statements, and journal-specific templates.  
**Exit criteria:** citation checks pass; claim-to-evidence traceability is available; fabricated-reference tests fail safely; external submissions remain approval-gated.

## Phase 13 — Evaluation, adversarial testing, and governance

**Build:** repeatable benchmark suite, security tests, misleading-source tests, prompt-injection resistance, audit review, and release criteria.  
**Exit criteria:** documented results and unresolved issues are reviewed; critical risks are addressed; benchmarks are versioned and do not rely solely on self-scoring.

## Phase 14 — Multidisciplinary expansion and advanced autonomy

**Build:** additional domain agents, specialized datasets/tools, advanced computational discovery, and, only where justified, approved physical research integrations.  
**Exit criteria:** each new domain has its own validation cases, tool constraints, risk assessment, and expert review path. Expansion is evidence-gated.

## Current implementation status

- **Phases 0–1 — foundation and application shell:** integrated into `main` through [PR #1](https://github.com/MDJTalha/Artificial-Scientist/pull/1). The merge-triggered CI run passed backend tests on Python 3.12 and 3.13 plus frontend type-check, unit tests, and production build.
- **Phase 2 — research records and provenance:** integrated into `main` through [PR #2](https://github.com/MDJTalha/Artificial-Scientist/pull/2). The recorded branch CI passed before merge; this does not by itself prove every longer-term data-governance exit criterion is complete.
- **Phase 3 — literature retrieval:** integrated into `main` through [PR #3](https://github.com/MDJTalha/Artificial-Scientist/pull/3). Provider and frontend CI passed before merge.
- **Phase 4 — knowledge graph and vocabulary:** integrated into `main` through [PR #4](https://github.com/MDJTalha/Artificial-Scientist/pull/4). Knowledge-graph and frontend CI passed before merge.
- **Phase 5 — mathematics and scientific tools:** integrated into `main` through [PR #5](https://github.com/MDJTalha/Artificial-Scientist/pull/5). Math-tool and frontend CI passed before merge; the post-merge `main` CI run also passed.
- **Phase 6 — controlled computational laboratory:** remains in progress in [PR #6](https://github.com/MDJTalha/Artificial-Scientist/pull/6), targeting `main`. It currently supports allowlisted declarative math runs, durable SQLite records, canonical JSON result artifacts, SHA-256 integrity checks, and provenance-linked retrieval. A regression test now verifies tampered persisted records return a controlled generic server error from the list API. The timeout implementation's CI passed on commit `91a3d8768058dfb63869af98b26fccde4c928a17`. The newer environment-manifest/replay-verification and legacy-record compatibility changes are awaiting fresh CI. OS-level CPU/memory isolation, authentication, general binary artifact lifecycle, interruption recovery, and cross-system audit linkage remain unresolved; Phase 6 must not be declared complete yet.

The status above reflects recorded repository evidence. Passing CI is necessary but does not prove scientific validity, production readiness, or completion of all phase exit criteria.

## Release gates

Before every material milestone, publish an internal evidence report containing: scope completed; commit/version; commands run; test counts and outcomes; failures; known limitations; dependency or data constraints; security and scientific-integrity risks; and the next smallest justified step.

Never claim a phase is complete merely because its UI or documentation exists. Capability and tests determine status.
