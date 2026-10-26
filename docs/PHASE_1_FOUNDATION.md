# Phase 1 — Core Application Foundation

**Status:** Implementation started; acceptance checks pending.  
**Scope:** A minimal working API, a dashboard that checks the real API, and automated project checks.

## Delivered in this phase branch

### Backend foundation

- Installable FastAPI package under backend/src.
- Environment-based application name, version, environment, and allowed-origin settings.
- API identity endpoint at GET /.
- Process health endpoint at GET /api/v1/health.
- Application-only readiness endpoint at GET /api/v1/ready.
- OpenAPI documentation from FastAPI.
- Automated tests for the API identity, health, readiness scope, and OpenAPI schema.

### Frontend foundation

- React and TypeScript dashboard scaffolded with Vite.
- Responsive overview layout for the scientific research project.
- Real HTTP health check against the backend.
- Loading, connected, and unavailable states, with a retry action.
- Clear labels to distinguish planned capabilities from implemented functionality.
- Unit tests for status text and state descriptions.

### Continuous integration

- Backend tests and lint checks on Python 3.12 and 3.13.
- Frontend type-check, unit-test, and production-build steps.
- Workflow uses read-only repository permissions.

## Run locally on Windows

### Terminal A: backend

From the repository root, run one command at a time:

    cd backend
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    python -m uvicorn artificial_scientist.main:app --reload

API: http://127.0.0.1:8000  
Interactive API docs: http://127.0.0.1:8000/docs

If Python 3.12 is not installed, use an installed supported Python version (3.12 or 3.13) and substitute its launcher command.

### Terminal B: frontend

From the repository root in a second PowerShell terminal:

    cd frontend
    npm install
    npm run dev

The development dashboard is served at http://127.0.0.1:5173.

If the API is running on a different address, create frontend/.env.local from frontend/.env.example and set VITE_API_BASE_URL to the intended API origin, then restart the frontend server.

## Commands for verification

Backend (from backend with its virtual environment active):

    pytest
    ruff check src tests

Frontend (from frontend):

    npm run typecheck
    npm test
    npm run build

The GitHub Actions workflow runs these checks automatically. Do not report checks as passing until the corresponding run result has been inspected.

## Acceptance criteria

- [ ] Backend package installs cleanly on Python 3.12 and 3.13.
- [ ] Health and readiness endpoints return their documented JSON.
- [ ] Readiness semantics do not falsely claim that models, data sources, or compute services are available.
- [ ] Frontend can represent checking, connected, and unavailable API states.
- [ ] Retry initiates a fresh request.
- [ ] Frontend type-check, unit tests, and production build pass.
- [ ] Backend lint and automated tests pass.
- [ ] No API credentials or private research data are committed.
- [ ] Actual CI results and remaining limitations are recorded.

## Explicit limitations

This phase does not implement a database, user authentication, research-task persistence, model calls, literature connectors, a knowledge graph, scientific calculations, agent orchestration, autonomous code execution, or publication submission. Those belong to later phases and must pass their own tests.

A successful foundation check confirms application behavior only. It is not evidence of scientific discovery, scientific accuracy, or production security.
