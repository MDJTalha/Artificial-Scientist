# Artificial Scientist

**An open research project exploring autonomous, multidisciplinary scientific discovery.**

Artificial Scientist is a research-first effort to build a system that can investigate scientific questions, retrieve and trace evidence, generate competing hypotheses, run controlled computational experiments, evaluate results, learn from validated findings, and prepare reproducible scientific reports.

This is **not a commercial SaaS product**. Its guiding objective is to contribute to trustworthy scientific knowledge and the betterment of humanity.

## Current status

**Phases 0–4 have recorded passing implementation CI checks. Phase 5 — Mathematics & Scientific Tools has passed its implementation and pull-request CI checks and is available as [draft Pull Request #5](https://github.com/MDJTalha/Artificial-Scientist/pull/5) for review. All phase pull requests remain unmerged by design.**

The foundation includes a FastAPI backend, health/readiness endpoints, a React + TypeScript overview dashboard that checks the actual local API, typed research records, SQLite provenance storage, and GitHub Actions verification.

Phase 3 adds OpenAlex and Crossref metadata search adapters, source normalization, DOI-based deduplication, and optional persistent source records. Phase 4 adds typed scientific concepts, a controlled vocabulary, evidence-linked relationship assertions, server-side concept search, and bounded graph-neighborhood traversal. Phase 4 CI passed 46 backend tests on Python 3.12 and 46 on Python 3.13, plus frontend type-checking, 6 frontend tests, and the production build; see the [verified run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40265564598). Phase 5 adds bounded symbolic and numerical math, descriptive statistics, allowlisted unit conversion, dimensional checks, and in-memory PNG plotting. Its implementation CI passed 75 backend tests on Python 3.12 and 75 on Python 3.13, plus frontend type-checking, 6 frontend tests, and the production build; see the [verified code run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40266731194) and [passing pull-request run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40266895491). Full-text ingestion, automated claim verification, autonomous hypothesis generation, a secured general-purpose experiment lab, and agent orchestration **are not implemented yet**. Planned capabilities are not presented as active features.

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

## Technology baseline

- **Core API:** Python 3.12+, FastAPI, Pydantic through FastAPI request/response validation
- **Interface:** React, TypeScript, Vite
- **Mathematical tools implemented in Phase 5:** NumPy, SciPy, SymPy, Pint, and Matplotlib for bounded symbolic/numeric calculations, descriptive statistics, unit checks, and function plots. pandas, machine learning, and broader scientific workflows remain future scope.
- **Persistence planned:** SQLite initially, behind repository interfaces that allow later migration
- **Models planned:** provider-independent adapters; optional local inference with Ollama
- **Workflow orchestration planned:** explicit, testable workflows; evaluate LangGraph when checkpointed orchestration is needed
- **Scholarly metadata connectors:** OpenAlex and Crossref are implemented in Phase 3; additional repositories and full-text handling remain future work
- **Verification:** pytest, Ruff, TypeScript type checking, frontend unit tests, production build, regression tests, and reproducibility checks

This stack is provisional. Add a dependency only when it solves a defined problem and can be tested. See [docs/TECHNOLOGY_DECISIONS.md](docs/TECHNOLOGY_DECISIONS.md).

## Run the Phase 1 foundation locally

Prerequisites: Python 3.12 or 3.13 and Node.js 24 with npm.

### Backend (first PowerShell terminal)

Run one command at a time from the repository root:

    cd backend
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    python -m uvicorn artificial_scientist.main:app --reload

API: http://127.0.0.1:8000  
Interactive API docs: http://127.0.0.1:8000/docs

### Frontend (second PowerShell terminal)

From the repository root:

    cd frontend
    npm install
    npm run dev

Dashboard: http://127.0.0.1:5173

If Python 3.12 is not installed, use Python 3.13 and its matching launcher command.

### Local verification

Backend, from the backend directory with the virtual environment active:

    pytest
    ruff check src tests

Frontend, from the frontend directory:

    npm run typecheck
    npm test
    npm run build

Passing these checks verifies the current application foundation only; it does not demonstrate scientific accuracy or discovery.

## Repository map

- [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) — mission, scope, principles, and success measures
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — proposed system boundaries and data flow
- [docs/PANELS.md](docs/PANELS.md) — purpose and responsibilities of the 12 planned workspaces
- [docs/ROADMAP.md](docs/ROADMAP.md) — 15 phases and acceptance gates
- [docs/TECHNOLOGY_DECISIONS.md](docs/TECHNOLOGY_DECISIONS.md) — provisional architecture decisions
- [docs/SCIENTIFIC_INTEGRITY_AND_SAFETY.md](docs/SCIENTIFIC_INTEGRITY_AND_SAFETY.md) — scientific integrity and safe autonomy requirements
- [docs/PHASE_1_FOUNDATION.md](docs/PHASE_1_FOUNDATION.md) — Phase 1 setup, test commands, accepted CI results, and limitations
- [docs/PHASE_2_RECORDS.md](docs/PHASE_2_RECORDS.md) — Phase 2 record schema, persistence, API examples, verified CI results, and limitations
- [backend/README.md](backend/README.md) — backend setup and endpoint reference
- [docs/PHASE_3_LITERATURE.md](docs/PHASE_3_LITERATURE.md) — scholarly search API, provenance, rate limits, and acceptance criteria
- [docs/PHASE_4_KNOWLEDGE_GRAPH.md](docs/PHASE_4_KNOWLEDGE_GRAPH.md) — concept schemas, controlled relations, graph API, verified CI results, and acceptance criteria
- [docs/PHASE_5_MATH_TOOLS.md](docs/PHASE_5_MATH_TOOLS.md) — mathematical API contracts, supported operations, safety bounds, numerical reference cases, and CI evidence
- [docs/PHASE_5_MATH_TOOLS.md](docs/PHASE_5_MATH_TOOLS.md) — mathematical API contracts, supported operations, safety bounds, numerical reference cases, and acceptance criteria

## Development approach

Build one end-to-end, measurable research workflow before expanding the interface or the number of agents. The first research prototype should accept a bounded computational question, retrieve traceable evidence, formulate a hypothesis, run an approved computation, validate the result, and export a reproducible report.

Never describe a proposed, drafted, or untested feature as implemented. Each milestone must report actual tests, observed results, known limitations, and outstanding risks.

## Non-goals for the initial milestone

- Training a frontier-scale foundation model from scratch.
- Claiming complete expertise in every scientific discipline.
- Unrestricted code execution, self-modification, or unsupervised physical experiments.
- Automatic external publication without review and authorization.
- Commercial monetization features.

## Contributing and licensing

The repository currently includes an MIT license. Before adding datasets, model weights, article text, or third-party code, review their licenses and use restrictions independently. Do not assume that the repository license relicenses external materials.
