# Backend

The backend is a Python/FastAPI foundation. It currently exposes API identity, health, and readiness endpoints only. It does not yet perform scientific research, call an LLM, query scholarly databases, or run experiments.

## Requirements

- Python 3.12 or 3.13
- Internet access during the first dependency installation

## Windows PowerShell setup

Run these commands from the repository root, one at a time:

    cd backend
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    python -m uvicorn artificial_scientist.main:app --reload

Open http://127.0.0.1:8000/docs for the generated API documentation.

If Python 3.12 is not installed, use an installed supported Python version (3.12 or 3.13) and substitute its launcher command.

## Endpoints

- GET / — minimal API identity response
- GET /api/v1/health — confirms the API process is responding
- GET /api/v1/ready — confirms the API application is ready to serve requests

Readiness currently checks only the application itself; it does not assert that databases, models, scientific sources, or compute services are available.

## Tests and quality checks

From the backend directory with the virtual environment active:

    pytest
    ruff check src tests

Do not treat passing API foundation tests as validation of scientific accuracy.
