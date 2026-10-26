# Backend

The backend is a Python/FastAPI research foundation with health/readiness endpoints, a local record/provenance API, a bounded OpenAlex/Crossref metadata search API,  a scientific knowledge graph API, and bounded mathematical and scientific computation endpoints. Research records, concepts, and relationships are stored immutably in SQLite with checksums and creation events. Concept search covers preferred labels, aliases, and definitions; graph links retain direction, evidence-source IDs, and assertion status. It does not download full-text papers, assess scientific truth, call an LLM, or run experiments.

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
- GET /api/v1/knowledge/vocabulary — list controlled concept/domain/predicate/status values
- POST /api/v1/knowledge/concepts — create an immutable scientific concept
- GET /api/v1/knowledge/concepts — search labels, aliases and definitions with optional domain/type/status filters
- GET /api/v1/knowledge/concepts/{concept_id} — retrieve and verify one concept
- POST /api/v1/knowledge/relationships — add an evidence-linkable relation between existing concepts
- GET /api/v1/knowledge/concepts/{concept_id}/relationships — list incoming/outgoing relations
- GET /api/v1/knowledge/graph/neighborhood?concept_id={uuid}&depth=1 — traverse a bounded concept neighborhood
- POST /api/v1/math/symbolic — restricted symbolic algebra, differentiation, integration, solving, substitution, and real evaluation
- POST /api/v1/math/numeric/integrate — definite numerical integration with error estimate and convergence status
- POST /api/v1/math/numeric/root — bracketed real root finding using Brent's method
- POST /api/v1/math/statistics — descriptive statistics and quartiles for bounded numeric samples
- POST /api/v1/math/plot — render a bounded real-valued function into an in-memory PNG image
- GET /api/v1/math/units — list supported unit tokens
- POST /api/v1/math/units/convert — convert compatible allowlisted units
- POST /api/v1/math/units/check — check dimensional compatibility of arithmetic expressions

Readiness currently checks only application configuration; it does not assert that remote scholarly APIs, models, or computational services are available. Literature search requires outbound internet access and may return partial or unavailable provider statuses. Records default to `data/artificial_scientist.sqlite3` relative to the backend working directory. Override with `ARTIFICIAL_SCIENTIST_DB_PATH` to select another path. The API is a local development foundation and has no authentication yet; do not expose it to untrusted networks.

## Tests and quality checks

From the backend directory with the virtual environment active:

    pytest
    ruff check src tests

Do not treat passing API foundation tests as validation of scientific accuracy.
