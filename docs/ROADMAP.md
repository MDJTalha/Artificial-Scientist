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

**Current implementation:** OpenAlex and Crossref metadata search adapters, bounded JSON handling, typed normalized results, DOI-based duplicate detection, SQLite source identity migration, provenance-carrying source records, and deterministic provider tests are implemented on `phase-3-literature-retrieval`. The phase remains in progress until current CI passes and the results are reviewed.

## Phase 4 — Knowledge and terminology

**Build:** structured scientific concepts, terminology, equation metadata, and supported relationships between concepts.  
**Exit criteria:** search and relationship tests pass; concept provenance is traceable; conflicting definitions are not silently merged.

## Phase 5 — Mathematics and scientific tools

**Build:** symbolic computation, numerical calculations, units/dimensional checks where supported, statistics, and plotting.  
**Exit criteria:** reference cases and numerical tolerances documented; independent checks used where feasible; failures and unsupported operations are explicit.

## Phase 6 — Controlled computational laboratory

**Build:** reproducible experiment configuration, managed dependencies, execution limits, logs, artifact capture, and an isolation strategy.  
**Exit criteria:** generated code cannot access unrestricted host resources; timeouts and resource limits tested; results can be traced to inputs and code. General agent-generated code is not enabled until the security boundary is reviewed.

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

- **Phase 0 — foundation documents:** established in the Phase 0–1 draft pull request.
- **Phase 1 — core application foundation:** CI passed on Python 3.12 and 3.13; frontend type-check, six unit tests, and production build passed on the recorded implementation commit.
- **Phase 2 — research records and provenance:** acceptance checks passed on the stacked phase branch; see the recorded [Phase 2 CI run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40263258124). Phase 2 remains a draft awaiting review/integration.
- **Phase 3 — literature retrieval:** OpenAlex/Crossref adapters, normalized source metadata, DOI deduplication, provider failure handling, and provenance-aware persistence are implemented in the current branch; see `docs/PHASE_3_LITERATURE.md`. Acceptance status depends on the latest CI run.

The status above reflects recorded repository evidence. It is not a declaration of scientific discovery capability.

## Release gates

Before every material milestone, publish an internal evidence report containing: scope completed; commit/version; commands run; test counts and outcomes; failures; known limitations; dependency or data constraints; security and scientific-integrity risks; and the next smallest justified step.

Never claim a phase is complete merely because its UI or documentation exists. Capability and tests determine status.
