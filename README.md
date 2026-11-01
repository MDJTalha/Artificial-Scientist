# Artificial Scientist

**An open research project exploring autonomous, multidisciplinary scientific discovery.**

Artificial Scientist is a research-first effort to build a system that can investigate scientific questions, retrieve and trace evidence, generate competing hypotheses, run controlled computational experiments, evaluate results, learn from validated findings, and prepare reproducible scientific reports.

This is **not a commercial SaaS product**. Its guiding objective is to contribute to trustworthy scientific knowledge and the betterment of humanity.

## Current status

The repository contains integrated implementations across Phases 0–14, with repository-side hardening and regression coverage for provenance, literature metadata, knowledge graphs, bounded mathematics, tenant-scoped records, hypothesis discovery, controlled autonomy, governance, and domain safety boundaries.

The current release posture is **evidence-gated, not production-certified**. Phase 6 intentionally fails closed for production-like execution until a reviewed OS-level sandbox is deployed and independently assessed. Remaining external gates include real OIDC/JWKS provider validation, sanitized migration/backup/restore/rollback rehearsal, operational deployment validation, independent security review, and scientific/domain-expert replication evidence.

Phase 7 now includes bounded research-question decomposition, competing-hypothesis assessment, falsification planning, bounded OpenAlex/Crossref prior-work screening, tenant-scoped evidence validation, and deterministic directional/null hypothesis suggestions. Generated suggestions are explicitly marked **requires human review** and make no claims of truth, causality, or novelty.

Phases 8–14 provide protected workflow orchestration, approval tokens, restart-recoverable tenant-scoped memory, independent verification, bounded specialist collaboration, evidence-linked scientific writing, benchmark/governance decisions, and an evidence-gated domain registry with a hard rejection boundary for physical actions. These controls do not certify scientific correctness or production security by themselves.

GitHub Actions remains the authoritative repository verification mechanism: every material branch or release candidate must pass the exact current commit on Python 3.12 and 3.13 plus frontend type-checking, tests, and production build before merge.

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
- **Persistence:** SQLite-backed repository stores are implemented for research provenance, lab runs, and governed autonomy; interfaces preserve a path to later migration
- **Models planned:** provider-independent adapters; optional local inference with Ollama
- **Workflow orchestration:** explicit, testable, bounded workflow engines with persistence and approval gates; no unrestricted agent execution
- **Scholarly metadata connectors:** OpenAlex and Crossref are implemented in Phase 3; additional repositories and full-text handling remain future work
- **Verification:** pytest, Ruff, TypeScript type checking, frontend unit tests, production build, regression tests, and reproducibility checks

This stack is provisional. Add a dependency only when it solves a defined problem and can be tested. See [docs/TECHNOLOGY_DECISIONS.md](docs/TECHNOLOGY_DECISIONS.md).

## Run the Phase 1 foundation locally

Prerequisites: Python 3.12 or 3.13 and Node.js 24 with npm.

### Backend (first PowerShell terminal)

Run one command at a time from the repository root:

    cd backend
    py -3.12 -m venv .venv
    .\\.venv\\Scripts\\Activate.ps1
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    $env:ARTIFICIAL_SCIENTIST_ENV = "development"
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
- [docs/BACKEND_DEPLOYMENT.md](docs/BACKEND_DEPLOYMENT.md) — container runtime, deployment architecture, and production release gates
- [docs/PHASE_3_LITERATURE.md](docs/PHASE_3_LITERATURE.md) — scholarly search API, provenance, rate limits, and acceptance criteria
- [docs/PHASE_4_KNOWLEDGE_GRAPH.md](docs/PHASE_4_KNOWLEDGE_GRAPH.md) — concept schemas, controlled relations, graph API, verified CI results, and acceptance criteria
- [docs/PHASE_5_MATH_TOOLS.md](docs/PHASE_5_MATH_TOOLS.md) — mathematical API contracts, supported operations, safety bounds, numerical reference cases, CI evidence, and acceptance criteria\n- [docs/PHASE_6_CONTROLLED_LAB.md](docs/PHASE_6_CONTROLLED_LAB.md) — declarative lab API, integrity hashes, security limitations, and phase exit gates\n- [docs/PHASE_7_HYPOTHESIS_DISCOVERY.md](docs/PHASE_7_HYPOTHESIS_DISCOVERY.md) — question decomposition, hypothesis assessment, OpenAlex/Crossref prior-work screening, rubric, persistence, examples, limitations, and acceptance criteria

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
