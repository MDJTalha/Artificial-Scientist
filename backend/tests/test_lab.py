"""Reference and adversarial tests for the controlled computational lab."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from artificial_scientist.api.routes.lab import get_lab_store
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabRunStore
from artificial_scientist.main import app


def test_lab_executes_allowlisted_steps_and_returns_trace_hashes() -> None:
    request = LabRunRequest(
        title="Reference derivative",
        steps=[
            {
                "step_id": "differentiate",
                "operation": "symbolic",
                "inputs": {
                    "operation": "differentiate",
                    "expression": "x**3",
                    "symbols": ["x"],
                    "variable": "x",
                },
            },
            {
                "step_id": "integral",
                "operation": "integrate",
                "inputs": {
                    "expression": "x**2",
                    "variable": "x",
                    "lower": 0,
                    "upper": 1,
                },
            },
        ],
        random_seed=7,
    )
    result = run_lab(request)
    assert result.status == "completed"
    assert len(result.configuration_sha256) == 64
    assert len(result.result_sha256) == 64
    assert result.steps[0].output is not None
    assert result.steps[0].output["result"] == "3*x**2"
    assert result.steps[1].output is not None
    assert result.steps[1].output["value"] == pytest.approx(1 / 3)
    assert any("status=completed" in line for line in result.logs)


def test_lab_stops_after_invalid_step_and_marks_later_steps_skipped() -> None:
    request = LabRunRequest(
        title="Failure handling",
        steps=[
            {
                "step_id": "invalid",
                "operation": "symbolic",
                "inputs": {"operation": "execute", "expression": "x"},
            },
            {
                "step_id": "later",
                "operation": "statistics",
                "inputs": {"values": [1, 2, 3]},
            },
        ],
    )
    result = run_lab(request)
    assert result.status == "failed"
    assert result.steps[0].status == "failed"
    assert result.steps[1].status == "skipped"


def test_lab_rejects_arbitrary_execution_operations_and_duplicate_ids() -> None:
    with pytest.raises(ValidationError):
        LabRunRequest(
            title="Arbitrary code is not supported",
            steps=[
                {
                    "step_id": "python",
                    "operation": "python",
                    "inputs": {"code": "import os"},
                }
            ],
        )
    with pytest.raises(ValidationError, match="unique"):
        LabRunRequest(
            title="Duplicate identifiers",
            steps=[
                {"step_id": "same", "operation": "statistics", "inputs": {"values": [1, 2]}},
                {"step_id": "same", "operation": "statistics", "inputs": {"values": [3, 4]}},
            ],
        )


def test_lab_enforces_step_count_and_configuration_size_limits() -> None:
    with pytest.raises(ValidationError):
        LabRunRequest(
            title="Too many steps",
            steps=[
                {
                    "step_id": f"step_{index}",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2]},
                }
                for index in range(21)
            ],
        )


def test_lab_api_returns_structured_run_response() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/lab/runs",
        json={
            "title": "API reference test",
            "steps": [
                {
                    "step_id": "stats",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3, 4], "variance_mode": "population"},
                }
            ],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["steps"][0]["output"]["mean"] == pytest.approx(2.5)
    assert len(payload["configuration_sha256"]) == 64



def test_lab_api_exposes_durable_result_artifact_and_provenance(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "api-lab-artifacts.sqlite3"))
    app.dependency_overrides[get_lab_store] = lambda: store
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/lab/runs",
            json={
                "title": "Artifact API test",
                "plan_record_id": "b1fce9e0-3c7c-4a7c-9b75-0a2a3a1e8c2f",
                "steps": [
                    {
                        "step_id": "stats",
                        "operation": "statistics",
                        "inputs": {"values": [2, 4, 6], "variance_mode": "population"},
                    }
                ],
            },
        )
        assert response.status_code == 201
        run = response.json()
        run_id = run["run_id"]

        listing = client.get(f"/api/v1/lab/runs/{run_id}/artifacts")
        assert listing.status_code == 200
        assert len(listing.json()) == 1
        metadata = listing.json()[0]
        assert metadata["provenance"]["plan_record_id"] == (
            "b1fce9e0-3c7c-4a7c-9b75-0a2a3a1e8c2f"
        )

        artifact_response = client.get(f"/api/v1/lab/artifacts/{metadata['artifact_id']}")
        assert artifact_response.status_code == 200
        artifact = artifact_response.json()
        assert artifact["sha256"] == metadata["sha256"]
        assert artifact["content"]["run_id"] == run_id
        assert artifact["content"]["result_sha256"] == run["result_sha256"]
    finally:
        app.dependency_overrides.pop(get_lab_store, None)
