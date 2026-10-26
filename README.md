# Artificial Scientist

**An open research project exploring autonomous, multidisciplinary scientific discovery.**

Artificial Scientist is a research-first effort to build a system that can investigate scientific questions, retrieve and trace evidence, generate competing hypotheses, run controlled computational experiments, evaluate results, learn from validated findings, and prepare reproducible scientific reports.

This is **not a commercial SaaS product**. Its guiding objective is to contribute to trustworthy scientific knowledge and the betterment of humanity.

## Current status

**Phase 0 — project definition and architecture.**

The repository is being established. At this stage, the project has foundational documentation only; a working scientific research engine, autonomous agents, and user interface have **not yet been implemented or validated**. Roadmap items are intentions, not completed capabilities.

## Scientific principles

- Evidence over confident-sounding answers.
- Falsification and competing explanations over confirmation alone.
- Reproducibility and provenance for material findings.
- Explicit uncertainty, limitations, negative results, and failures.
- Independent validation; agreement among AI agents is not proof.
- Controlled autonomy, security, and human authorization for consequential actions.
- Honest reporting: never invent sources, observations, experiments, or benchmark results.

## Planned research workspaces

1. Scientific Command Center
2. Research Agenda & Problem Observatory
3. Literature & Evidence Explorer
4. Scientific Knowledge Graph & Vocabulary
5. Hypothesis & Discovery Lab
6. Mathematics & Formal Reasoning Workbench
7. Computational Laboratory & Simulation Center
8. Data Analysis & Results Observatory
9. Experiment Journal & Reproducibility
10. Scientific Memory & Learning
11. Scientific Manuscript & Publication Studio
12. Independent Review, Evaluation & Governance

These are intended workspaces, not a promise that all capabilities will exist in the first release. Shared research services and verifiable workflows take priority over building empty screens.

## Development roadmap

The plan is organized into **15 phases (Phase 0 through Phase 14)**, with acceptance criteria at every stage:

- **0–2:** Charter, architecture, core infrastructure, and research provenance.
- **3–6:** Literature retrieval, scientific knowledge, mathematical tools, and a controlled computational lab.
- **7–10:** Hypothesis discovery, experiment planning, independent analysis, and controlled memory.
- **11–13:** Multi-agent collaboration, scientific writing, evaluation, and adversarial testing.
- **14:** Evidence-gated expansion to more disciplines and advanced autonomy.

See [docs/ROADMAP.md](docs/ROADMAP.md) for phase goals and exit criteria.

## Proposed technology baseline

- **Core:** Python, FastAPI, Pydantic
- **Interface:** React, TypeScript, Vite
- **Scientific computing:** NumPy, SciPy, SymPy, pandas, Matplotlib; scikit-learn initially
- **Persistence:** SQLite initially, behind repository interfaces that allow later migration
- **Models:** provider-independent adapters; optional local inference with Ollama
- **Workflow orchestration:** start with explicit, testable workflows; evaluate LangGraph when checkpointed multi-step orchestration is needed
- **Research sources:** lawful, source-aware connectors such as OpenAlex, Crossref, and selected repositories
- **Verification:** pytest, type checking, linting, regression tests, artifact hashes, and reproducibility checks

This stack is provisional. Add a dependency only when it solves a defined problem and can be tested. See [docs/TECHNOLOGY_DECISIONS.md](docs/TECHNOLOGY_DECISIONS.md).

## Repository map

- [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) — mission, scope, principles, and success measures
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — proposed system boundaries and data flow
- [docs/PANELS.md](docs/PANELS.md) — purpose and responsibilities of the 12 planned workspaces
- [docs/ROADMAP.md](docs/ROADMAP.md) — 15 phases and acceptance gates
- [docs/TECHNOLOGY_DECISIONS.md](docs/TECHNOLOGY_DECISIONS.md) — provisional architecture decisions
- [docs/SCIENTIFIC_INTEGRITY_AND_SAFETY.md](docs/SCIENTIFIC_INTEGRITY_AND_SAFETY.md) — scientific integrity and safe autonomy requirements

## Development approach

Build one end-to-end, measurable research workflow before expanding the interface or the number of agents. The first prototype should accept a bounded computational research question, retrieve traceable evidence, formulate a hypothesis, run an approved computation, validate the result, and export a reproducible report.

Never describe a proposed, drafted, or untested feature as implemented. Each milestone must report actual tests, observed results, known limitations, and outstanding risks.

## Non-goals for the initial milestone

- Training a frontier-scale foundation model from scratch.
- Claiming complete expertise in every scientific discipline.
- Unrestricted code execution, self-modification, or unsupervised physical experiments.
- Automatic external publication without review and authorization.
- Commercial monetization features.

## Contributing and licensing

The repository currently includes an MIT license. Before adding datasets, model weights, article text, or third-party code, review their licenses and use restrictions independently. Do not assume that the repository license relicenses external materials.
