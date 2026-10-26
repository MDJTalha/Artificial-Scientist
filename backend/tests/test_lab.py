"""Reference and adversarial tests for the controlled computational lab."""

import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from artificial_scientist.api.routes import lab as lab_routes
from artificial_scientist.api.routes.lab import get_lab_store
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.execution import LabExecutionTimeout, run_isolated
from artificial_scientist.lab.integrity import result_digest
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabArtifactNotFound, LabRunStore
from artificial_scientist.main import app


def _slow_lab_worker() -> dict[str, object]:
    import time

    time.sleep(2)
    return {"completed": True}


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




def test_lab_run_records_manifest_and_verification_replays_outputs(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "lab-verification.sqlite3"))
    app.dependency_overrides[get_lab_store] = lambda: store
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/lab/runs",
            json={
                "title": "Replay verification",
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
        assert run["configuration"]["title"] == "Replay verification"
        assert run["environment_manifest"]["python_version"]
        assert run["environment_manifest"]["package:numpy"]

        verification = client.post(f"/api/v1/lab/runs/{run['run_id']}/verify")
        assert verification.status_code == 200
        result = verification.json()
        assert result["reproducible"] is True
        assert result["configuration_matches"] is True
        assert result["environment_matches"] is True
        assert result["outputs_match"] is True
        assert result["differences"] == []
    finally:
        app.dependency_overrides.pop(get_lab_store, None)


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



def test_store_verifies_legacy_run_payloads_without_new_manifest_fields(tmp_path) -> None:
    database = str(tmp_path / "legacy-lab-record.sqlite3")
    store = LabRunStore(database)
    from artificial_scientist.lab.engine import run_lab

    run = run_lab(
        LabRunRequest(
            title="Legacy record compatibility",
            steps=[
                {
                    "step_id": "stats",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3]},
                }
            ],
        )
    )
    store.save(run)
    legacy_payload = run.model_dump(mode="json")
    legacy_payload.pop("configuration")
    legacy_payload.pop("environment_manifest")
    legacy_payload["result_sha256"] = result_digest(legacy_payload)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE lab_runs SET payload_json = ? WHERE run_id = ?",
            (json.dumps(legacy_payload), str(run.run_id)),
        )

    restored = store.get(run.run_id)
    assert restored.run_id == run.run_id
    assert restored.configuration == {}
    assert restored.environment_manifest == {}


def test_lab_api_returns_generic_server_error_for_tampered_run_listing(tmp_path) -> None:
    database = str(tmp_path / "tampered-lab-list.sqlite3")
    store = LabRunStore(database)
    app.dependency_overrides[get_lab_store] = lambda: store
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/lab/runs",
            json={
                "title": "Integrity listing test",
                "steps": [
                    {
                        "step_id": "stats",
                        "operation": "statistics",
                        "inputs": {"values": [1, 2, 3]},
                    }
                ],
            },
        )
        assert response.status_code == 201
        run_id = response.json()["run_id"]

        with sqlite3.connect(database) as connection:
            row = connection.execute(
                "SELECT payload_json FROM lab_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            payload = json.loads(row[0])
            payload["title"] = "Tampered title"
            connection.execute(
                "UPDATE lab_runs SET payload_json = ? WHERE run_id = ?",
                (json.dumps(payload), run_id),
            )

        listing = client.get("/api/v1/lab/runs")
        assert listing.status_code == 500
        assert listing.json()["detail"] == "Stored lab run failed integrity validation."
    finally:
        app.dependency_overrides.pop(get_lab_store, None)

def test_isolated_lab_worker_respects_deadline() -> None:
    import time

    started = time.monotonic()
    with pytest.raises(LabExecutionTimeout, match="execution deadline"):
        run_isolated(_slow_lab_worker, (), timeout_seconds=0.1)
    assert time.monotonic() - started < 5

def test_lab_request_bounds_per_step_timeout() -> None:
    with pytest.raises(ValidationError):
        LabRunRequest(
            title="Excessive timeout",
            step_timeout_seconds=30.1,
            steps=[
                {
                    "step_id": "stats",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3]},
                }
            ],
        )



def test_lab_replay_verification_rejects_legacy_record_without_configuration(tmp_path) -> None:
    database = str(tmp_path / "legacy-replay.sqlite3")
    store = LabRunStore(database)
    run = run_lab(
        LabRunRequest(
            title="Legacy replay is unavailable",
            steps=[
                {
                    "step_id": "stats",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3]},
                }
            ],
        )
    )
    store.save(run)
    legacy_payload = run.model_dump(mode="json")
    legacy_payload.pop("configuration")
    legacy_payload.pop("environment_manifest")
    legacy_payload["result_sha256"] = result_digest(legacy_payload)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE lab_runs SET payload_json = ? WHERE run_id = ?",
            (json.dumps(legacy_payload), str(run.run_id)),
        )

    app.dependency_overrides[get_lab_store] = lambda: store
    client = TestClient(app)
    try:
        response = client.post(f"/api/v1/lab/runs/{run.run_id}/verify")
        assert response.status_code == 409
        assert response.json()["detail"] == (
            "This stored run predates replayable configuration metadata."
        )
    finally:
        app.dependency_overrides.pop(get_lab_store, None)


def test_retention_purge_deletes_artifacts_and_preserves_audit_tombstone(tmp_path) -> None:
    database = str(tmp_path / "lab-retention.sqlite3")
    store = LabRunStore(database)
    run = run_lab(
        LabRunRequest(
            title="Expired retention fixture",
            steps=[
                {
                    "step_id": "stats",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3]},
                }
            ],
        )
    )
    store.save(run)
    artifact_id = store.list_artifacts(run.run_id)[0].artifact_id
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE lab_runs SET created_at = ? WHERE run_id = ?",
            ("2020-01-01T00:00:00+00:00", str(run.run_id)),
        )

    deleted = store.purge_runs_before(
        "2021-01-01T00:00:00+00:00",
        limit=10,
        reason="test_retention",
    )
    assert deleted == [str(run.run_id)]
    with sqlite3.connect(database) as connection:
        run_count = connection.execute(
            "SELECT COUNT(*) FROM lab_runs WHERE run_id = ?", (str(run.run_id),)
        ).fetchone()[0]
        artifact_count = connection.execute(
            "SELECT COUNT(*) FROM lab_artifacts WHERE run_id = ?", (str(run.run_id),)
        ).fetchone()[0]
        tombstone = connection.execute(
            """
            SELECT result_sha256, configuration_sha256, retention_cutoff,
                   reason, artifacts_deleted
            FROM lab_run_retention_events WHERE run_id = ?
            """,
            (str(run.run_id),),
        ).fetchone()
    assert run_count == 0
    assert artifact_count == 0
    assert tombstone == (
        run.result_sha256,
        run.configuration_sha256,
        "2021-01-01T00:00:00+00:00",
        "test_retention",
        1,
    )
    with pytest.raises(LabArtifactNotFound):
        store.get_artifact(artifact_id)


def test_retention_purge_requires_timezone_and_bounded_limit(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "lab-retention-validation.sqlite3"))
    with pytest.raises(ValueError, match="timezone"):
        store.purge_runs_before("2021-01-01T00:00:00")
    with pytest.raises(ValueError, match="between 1 and 100"):
        store.purge_runs_before("2021-01-01T00:00:00+00:00", limit=101)



def test_lab_api_requires_constant_time_key_outside_development(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        lab_routes,
        "get_settings",
        lambda: SimpleNamespace(environment="production", lab_api_key="test-secret"),
    )
    store = LabRunStore(str(tmp_path / "authenticated-lab.sqlite3"))
    app.dependency_overrides[get_lab_store] = lambda: store
    client = TestClient(app)
    try:
        assert client.get("/api/v1/lab/runs").status_code == 401
        assert client.get(
            "/api/v1/lab/runs", headers={"X-Lab-API-Key": "wrong"}
        ).status_code == 401
        accepted = client.get(
            "/api/v1/lab/runs", headers={"X-Lab-API-Key": "test-secret"}
        )
        assert accepted.status_code == 200
    finally:
        app.dependency_overrides.pop(get_lab_store, None)


def test_lab_api_fails_closed_when_production_key_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        lab_routes,
        "get_settings",
        lambda: SimpleNamespace(environment="production", lab_api_key=None),
    )
    response = TestClient(app).get("/api/v1/lab/runs")
    assert response.status_code == 503
    assert response.json()["detail"] == "Lab API authentication is not configured."



def test_lab_run_rejects_request_body_over_64_kib_before_validation() -> None:
    response = TestClient(app).post(
        "/api/v1/lab/runs",
        json={"title": "x" * (65 * 1024), "steps": []},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == (
        "Lab run request body exceeds the 65536-byte limit."
    )
