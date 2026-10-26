# Backend

The backend is a Python/FastAPI research foundation with health/readiness endpoints, a local record/provenance API, and a bounded scholarly metadata search API for OpenAlex and Crossref. The record API validates typed research records and relationships, persists them in SQLite, hashes stored payloads, and records creation events. Literature search normalizes provider metadata, records retrieval provenance, and can persist source records. It does not download full-text papers, assess scientific truth, call an LLM, or run experiments.

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
- POST /api/v1/records — create a typed, validated research record
- GET /api/v1/records — list records, optionally filtered by record type
- GET /api/v1/records/{record_id} — fetch and verify a record's SHA-256 payload checksum and schema
- GET /api/v1/records/audit-events — list server-generated creation audit events
- POST /api/v1/literature/search — search OpenAlex and/or Crossref, normalize metadata, deduplicate results, and optionally persist source records

Readiness currently checks only application configuration; it does not assert that remote scholarly APIs, models, or computational services are available. Literature search requires outbound internet access and may return partial or unavailable provider statuses. Records default to `data/artificial_scientist.sqlite3` relative to the backend working directory. Override with `ARTIFICIAL_SCIENTIST_DB_PATH` to select another path. The API is a local development foundation and has no authentication yet; do not expose it to untrusted networks.

## Tests and quality checks

From the backend directory with the virtual environment active:

    pytest
    ruff check src tests

Do not treat passing API foundation tests as validation of scientific accuracy.
