"""Reference and adversarial tests for the controlled computational lab."""

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.models import LabRunRequest
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
