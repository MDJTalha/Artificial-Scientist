# Provisional Technology Decisions

**Status:** Initial proposals, subject to validation  
**Decision date:** 2026-10-26

The goal is a lightweight, replaceable, research-oriented system that can start on a modest Windows machine. Avoid unnecessary dependencies. Validate versions and licenses when implementation begins.

## ADR-001 — Python for the scientific core

**Decision:** Use Python for backend orchestration and scientific tooling.

**Rationale:** Python has a mature ecosystem for scientific computing, data processing, machine learning, and research automation.

**Initial tools:** FastAPI for HTTP APIs; Pydantic for validated data structures; pytest for testing; Ruff and a static type checker for quality checks.

**Trade-offs:** Python environments and dependencies require careful locking; execution isolation must be designed separately from ordinary backend processes.

## ADR-002 — React, TypeScript, and Vite for the interface

**Decision:** Use React with TypeScript and Vite for the research workspace.

**Rationale:** A component-based UI can support the planned workspaces without requiring a commercial platform or server-rendering infrastructure at the outset.

**Candidate styling:** Tailwind CSS and an accessible component library, selected and pinned when the UI milestone begins.

**Trade-offs:** There are separate frontend dependencies and build tooling; do not build all panels before services work.

## ADR-003 — SQLite as the initial structured store

**Decision:** Start with SQLite behind a repository/data-access layer.

**Rationale:** Low operational cost and no separate database service are suitable for an initial local research prototype.

**Migration path:** Evaluate PostgreSQL when concurrent access, data volume, reliability, or multi-user requirements justify it.

**Trade-offs:** SQLite is not the assumption for every future scale pattern. Backups, schema migrations, and write contention must be tested.

## ADR-004 — Explicit research workflows before elaborate agent frameworks

**Decision:** Model research as typed, stateful steps with clear inputs, outputs, failure states, checkpointing, and approval gates. Evaluate LangGraph or an equivalent framework when real workflow complexity justifies it.

**Rationale:** This avoids premature abstraction and makes behavior easier to test.

**Trade-offs:** Early orchestration may require more explicit code. Any selected framework remains an implementation detail and must not own the scientific truth or policy decisions.

## ADR-005 — Model-provider independence and local inference

**Decision:** Use a model gateway with adapters; make local inference through Ollama an optional development mode. Remote models may be added behind the same interface, with explicit configuration and spending controls.

**Rationale:** Model capabilities, hardware needs, licenses, and cost change. The project should be able to compare models rather than depend on one.

**Trade-offs:** Local models may be limited by RAM and may perform poorly on complex reasoning. Remote models can require payment, transmit data outside the machine, or have usage limits. No model should be assumed to have been tested until it is.

## ADR-006 — Established scientific libraries before custom ML

**Decision:** Begin with relevant established tools: NumPy, SciPy, SymPy, pandas, Matplotlib, and statsmodels; use scikit-learn for initial ML experiments. Introduce PyTorch or domain-specific packages when a validated use case needs them.

**Rationale:** Known numerical and symbolic tools provide a more reliable foundation than asking an LLM to perform all calculations in natural language.

**Trade-offs:** Tool outputs still require correct setup, domain assumptions, and verification. Not every library is appropriate for every discipline.

## ADR-007 — Scholarly metadata connectors and source traceability

**Decision:** Implement source adapters rather than hard-code one literature provider. Candidate sources include OpenAlex, Crossref, arXiv, and later domain-specific repositories.

**Rationale:** Sources differ in coverage, access, metadata quality, and correction records.

**Requirements:** Follow API terms and rate limits; preserve identifiers and retrieval time; check licenses and full-text access; do not imply coverage is exhaustive.

## ADR-008 — Isolated and permissioned execution

**Decision:** Keep computation separate from the API process and host filesystem. Start with tightly constrained predefined calculations. Do not allow unrestricted execution of arbitrary agent-generated code.

**Rationale:** Research-code execution creates security, privacy, and machine-stability risks.

**Exit condition for broader execution:** Isolation boundary, resource limits, network policy, file access, dependency installation, cleanup, logging, and adversarial tests must be reviewed before widening permissions.

## ADR-009 — Provenance and evaluation as first-class features

**Decision:** Every major result must be linked to the model/tool versions, sources, inputs, parameters, code, outputs, verification checks, and limitations that produced it.

**Rationale:** A research system is only useful if its findings can be challenged, inspected, and reproduced.

**Trade-offs:** Provenance increases storage and implementation effort. Redact secrets and minimize sensitive data.

## Review policy

Revisit a decision when evidence, testing, or operational constraints justify it. Record the reason, alternatives considered, migration impact, and tests needed. Avoid adopting a dependency solely because it is popular.
