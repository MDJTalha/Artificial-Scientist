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

## Phase 6 — Controlled computational laboratory\n\n**Initial implementation:** `phase-6-controlled-lab` adds `POST /api/v1/lab/runs`, a bounded declarative runner for the existing symbolic, integration, root-finding, statistics, and unit-conversion operations. It validates typed inputs, caps runs at 20 steps and 64 KiB, stops after the first failed step, records per-step status/duration and diagnostic logs, and hashes canonicalized configuration/results. It does not execute arbitrary Python. SQLite run persistence, paginated retrieval, and stored result-digest verification are implemented. Durable artifact blobs, hard process timeouts, OS-level resource isolation, reproducible environment manifests, and fresh passing CI remain outstanding; therefore Phase 6 is **in progress, not complete**. See `docs/PHASE_6_CONTROLLED_LAB.md`.\n\n## Phase 7 — Hypothesis and discovery engine

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

- **Phase 0 — foundation documents:** established in the Phase 0–1 draft pull request.
- **Phase 1 — core application foundation:** CI passed on Python 3.12 and 3.13; frontend type-check, six unit tests, and production build passed on the recorded implementation commit.
- **Phase 2 — research records and provenance:** acceptance checks passed on the stacked phase branch; see the recorded [Phase 2 CI run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40263258124). Phase 2 remains a draft awaiting review/integration.
- **Phase 3 — literature retrieval:** implementation tests passed on code commit `a3d139a56526ad0d512ab568c1dca71cba815b8a`; see the [passing CI run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40264595989) and `docs/PHASE_3_LITERATURE.md`. It is awaiting review/integration.

- **Phase 4 — knowledge graph and vocabulary:** implementation tests passed on code commit `2e652fd211c0b32d4dd77bace69240223c3cbccb`; see the [passing CI run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40265564598) and `docs/PHASE_4_KNOWLEDGE_GRAPH.md`. Pull Request #4 is draft and targets Phase 3; it is not merged.

- **Phase 5 — mathematics and scientific tools:** core implementation CI passed on commit `bdf3dfffea45ed428fcb21667d282c035fc8d49d`; see the [passing run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40266731194) and `docs/PHASE_5_MATH_TOOLS.md`. Draft Pull Request #5 targets Phase 4; it remains unmerged.\n\n- **Phase 6 — controlled computational laboratory:** declarative runs, SQLite persistence, canonical JSON result artifacts, artifact retrieval APIs, digest verification, and run/plan/step provenance are implemented on `phase-6-controlled-lab`. The artifact-storage head is awaiting fresh CI verification; general binary artifacts, hard timeouts, OS isolation, and reproducible environment manifests remain outstanding. It remains in progress.

The status above reflects recorded repository evidence. It is not a declaration of scientific discovery capability.

## Release gates

Before every material milestone, publish an internal evidence report containing: scope completed; commit/version; commands run; test counts and outcomes; failures; known limitations; dependency or data constraints; security and scientific-integrity risks; and the next smallest justified step.

Never claim a phase is complete merely because its UI or documentation exists. Capability and tests determine status.
