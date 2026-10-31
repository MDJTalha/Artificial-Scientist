"""Reference and adversarial tests for the controlled computational lab."""

import asyncio
import hashlib
import io
import json
import sqlite3
import zipfile
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from artificial_scientist.api.routes import lab as lab_routes
from artificial_scientist.api.routes.lab import get_lab_store
from artificial_scientist.config import get_settings
from artificial_scientist.lab import execution as lab_execution
from artificial_scientist.lab import scanning as lab_scanning
from artificial_scientist.lab import store as lab_store_module
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.execution import LabExecutionTimeout, _stop_process, run_isolated
from artificial_scientist.lab.integrity import result_digest
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import (
    LabArtifactNotFound,
    LabExecutionNotFound,
    LabRunNotFound,
    LabRunStore,
)
from artificial_scientist.main import LabRequestBodyLimitMiddleware, app


@pytest.fixture(autouse=True)
def opt_in_to_development_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_ENV", "development")


def _slow_lab_worker() -> dict[str, object]:
    import time

    time.sleep(2)
    return {"completed": True}


def _multiline_error_lab_worker() -> dict[str, object]:
    raise ValueError("line one\nline two")


def _crash_lab_worker() -> dict[str, object]:
    import os

    os._exit(7)


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


def test_missing_environment_defaults_to_protected_lab_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ARTIFICIAL_SCIENTIST_ENV")
    monkeypatch.delenv("ARTIFICIAL_SCIENTIST_LAB_API_KEY", raising=False)
    monkeypatch.delenv("ARTIFICIAL_SCIENTIST_OIDC_ISSUER", raising=False)
    monkeypatch.delenv("ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE", raising=False)
    monkeypatch.delenv("ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL", raising=False)

    assert get_settings().environment == "production"
    response = TestClient(app).get("/api/v1/lab/runs")
    assert response.status_code == 503
    assert response.json()["detail"] == "Lab API authentication is not configured."




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


def test_lab_export_contains_run_artifact_and_checksum_manifest(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "lab-export.sqlite3"))
    app.dependency_overrides[get_lab_store] = lambda: store
    client = TestClient(app)
    try:
        created = client.post(
            "/api/v1/lab/runs",
            json={
                "title": "Export manifest test",
                "steps": [
                    {
                        "step_id": "stats",
                        "operation": "statistics",
                        "inputs": {"values": [2, 4, 6]},
                    }
                ],
            },
        )
        assert created.status_code == 201
        run_id = created.json()["run_id"]

        binary_payload = b"exported binary evidence\\x00\\x02"
        binary_upload = client.post(
            f"/api/v1/lab/runs/{run_id}/binary-artifacts?filename=evidence.bin",
            content=binary_payload,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert binary_upload.status_code == 201

        response = client.get(f"/api/v1/lab/runs/{run_id}/export")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            binary_path = f"binary/{binary_upload.json()['artifact_id']}-evidence.bin"
            assert set(archive.namelist()) == {
                "run.json",
                "artifacts.json",
                "binary-artifacts.json",
                "manifest.json",
                binary_path,
            }
            run_document = json.loads(archive.read("run.json"))
            artifact_documents = json.loads(archive.read("artifacts.json"))
            binary_metadata = json.loads(archive.read("binary-artifacts.json"))
            manifest = json.loads(archive.read("manifest.json"))
            assert run_document["run_id"] == run_id
            assert artifact_documents[0]["content"]["run_id"] == run_id
            assert binary_metadata[0]["sha256"] == hashlib.sha256(binary_payload).hexdigest()
            assert archive.read(binary_path) == binary_payload
            for name in ("run.json", "artifacts.json", "binary-artifacts.json", binary_path):
                payload = archive.read(name)
                assert manifest["files"][name]["sha256"] == hashlib.sha256(payload).hexdigest()
                assert manifest["files"][name]["size_bytes"] == len(payload)
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

def test_posix_worker_resource_limits_are_configured(monkeypatch) -> None:
    if lab_execution.resource is None:
        pytest.skip("POSIX resource limits are unavailable on this platform")
    configured: dict[int, tuple[int, int]] = {}

    monkeypatch.setattr(lab_execution.os, "name", "posix")
    monkeypatch.setattr(
        lab_execution.resource,
        "getrlimit",
        lambda _limit: (lab_execution.resource.RLIM_INFINITY, lab_execution.resource.RLIM_INFINITY),
    )
    monkeypatch.setattr(
        lab_execution.resource,
        "setrlimit",
        lambda limit, bounds: configured.__setitem__(limit, bounds),
    )

    lab_execution._apply_worker_resource_limits()

    assert configured[lab_execution.resource.RLIMIT_CPU] == (
        lab_execution._WORKER_CPU_SECONDS,
        lab_execution._WORKER_CPU_SECONDS,
    )
    assert configured[lab_execution.resource.RLIMIT_AS] == (
        lab_execution._WORKER_ADDRESS_SPACE_BYTES,
        lab_execution._WORKER_ADDRESS_SPACE_BYTES,
    )
    assert configured[lab_execution.resource.RLIMIT_FSIZE] == (
        lab_execution._WORKER_FILE_SIZE_BYTES,
        lab_execution._WORKER_FILE_SIZE_BYTES,
    )
    assert configured[lab_execution.resource.RLIMIT_NOFILE] == (
        lab_execution._WORKER_OPEN_FILES,
        lab_execution._WORKER_OPEN_FILES,
    )


def test_worker_cleanup_escalates_from_terminate_to_kill() -> None:
    class StubbornProcess:
        def __init__(self) -> None:
            self.alive = True
            self.terminate_called = False
            self.kill_called = False
            self.join_calls: list[float] = []

        def is_alive(self) -> bool:
            return self.alive

        def terminate(self) -> None:
            self.terminate_called = True

        def join(self, timeout: float) -> None:
            self.join_calls.append(timeout)

        def kill(self) -> None:
            self.kill_called = True
            self.alive = False

    process = StubbornProcess()
    _stop_process(process)
    assert process.terminate_called is True
    assert process.kill_called is True
    assert process.join_calls == [2, 2]


@pytest.mark.parametrize(
    "timeout_seconds", [0, -1, float("nan"), float("inf"), -float("inf")]
)
def test_isolated_lab_worker_rejects_invalid_deadlines(timeout_seconds: float) -> None:
    from artificial_scientist.lab.execution import LabExecutionError

    with pytest.raises(LabExecutionError, match="finite positive number"):
        run_isolated(_slow_lab_worker, (), timeout_seconds=timeout_seconds)


def test_isolated_worker_reports_unexpected_child_exit() -> None:
    from artificial_scientist.lab.execution import LabExecutionError

    with pytest.raises(LabExecutionError, match="exited without a result"):
        run_isolated(_crash_lab_worker, (), timeout_seconds=2)


def test_isolated_worker_normalizes_multiline_error_messages() -> None:
    from artificial_scientist.lab.execution import LabExecutionError

    with pytest.raises(LabExecutionError) as error:
        run_isolated(_multiline_error_lab_worker, (), timeout_seconds=2)

    assert "line one line two" in str(error.value)
    assert "\n" not in str(error.value)


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
    store.begin_execution(
        run.run_id,
        LabRunRequest(
            title="Expired retention fixture",
            steps=[
                {
                    "step_id": "stats",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3]},
                }
            ],
        ),
    )
    store.save(run)
    artifact_id = store.list_artifacts(run.run_id)[0].artifact_id
    store.save_binary_artifact(
        run.run_id,
        "retention-evidence.bin",
        "application/octet-stream",
        b"retention fixture",
    )
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
        retained_attempt = connection.execute(
            """
            SELECT status, configuration_sha256, result_sha256, request_json
            FROM lab_execution_attempts WHERE run_id = ?
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
        2,
    )
    assert retained_attempt == (
        "completed",
        run.configuration_sha256,
        run.result_sha256,
        "{}",
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
    database_path = str(tmp_path / "authenticated-lab.sqlite3")
    monkeypatch.setattr(
        lab_routes,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            lab_api_key="test-secret-value-that-is-at-least-32-chars",
            database_path=database_path,
        ),
    )
    store = LabRunStore(database_path)
    # A valid deployment API key authenticates the legacy principal, but it must
    # not bypass production tenant membership and role authorization.
    from artificial_scientist.authorization import TenantDirectory

    directory = TenantDirectory(database_path)
    principal_id = directory.register_principal(
        "deployment-configured", "legacy-shared-api-key"
    )
    tenant_id = directory.create_tenant("test-tenant", "Test Tenant")
    directory.grant_membership(principal_id, tenant_id, "researcher")

    app.dependency_overrides[get_lab_store] = lambda: store
    client = TestClient(app)
    headers = {
        "X-Lab-API-Key": "test-secret-value-that-is-at-least-32-chars",
        "X-Tenant-ID": tenant_id,
    }
    try:
        assert client.get("/api/v1/lab/runs").status_code == 401
        assert client.get(
            "/api/v1/lab/runs", headers={"X-Lab-API-Key": "wrong"}
        ).status_code == 401
        denied_without_tenant = client.get(
            "/api/v1/lab/runs",
            headers={"X-Lab-API-Key": "test-secret-value-that-is-at-least-32-chars"},
        )
        # A valid deployment key authenticates the request but does not select
        # an authorized tenant.
        assert denied_without_tenant.status_code == 403
        assert (
            denied_without_tenant.json()["detail"]
            == "Authenticated tenant membership is required."
        )
        accepted = client.get("/api/v1/lab/runs", headers=headers)
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


def test_lab_api_fails_closed_when_production_key_is_too_short(monkeypatch) -> None:
    monkeypatch.setattr(
        lab_routes,
        "get_settings",
        lambda: SimpleNamespace(environment="production", lab_api_key="short-key"),
    )
    response = TestClient(app).get(
        "/api/v1/lab/runs",
        headers={"X-Lab-API-Key": "short-key"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Lab API authentication requires a configured key of at least 32 characters."
    )



def test_lab_body_limit_rejects_chunked_body_without_content_length() -> None:
    messages = [
        {"type": "http.request", "body": b"a" * (40 * 1024), "more_body": True},
        {"type": "http.request", "body": b"b" * (30 * 1024), "more_body": False},
    ]
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return messages.pop(0)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    async def downstream(scope, receive, send) -> None:
        raise AssertionError("Oversized request must be rejected before the app.")

    middleware = LabRequestBodyLimitMiddleware(downstream)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/lab/runs",
        "headers": [],
    }
    asyncio.run(middleware(scope, receive, send))
    assert sent[0]["status"] == 413
    assert b"65536-byte limit" in sent[1]["body"]


def test_lab_run_rejects_request_body_over_64_kib_before_validation() -> None:
    response = TestClient(app).post(
        "/api/v1/lab/runs",
        json={"title": "x" * (65 * 1024), "steps": []},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == (
        "Lab run request body exceeds the 65536-byte limit."
    )



def test_opt_in_retention_job_removes_only_expired_runs_and_keeps_tombstones(tmp_path) -> None:
    from datetime import UTC, datetime

    from artificial_scientist.lab.retention import run_retention

    store = LabRunStore(str(tmp_path / "scheduled-retention.sqlite3"))
    old_run = run_lab(
        LabRunRequest(
            title="Expired scheduled retention fixture",
            steps=[
                {
                    "step_id": "stats",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3]},
                }
            ],
        )
    )
    recent_run = run_lab(
        LabRunRequest(
            title="Recent retention fixture",
            steps=[
                {
                    "step_id": "stats",
                    "operation": "statistics",
                    "inputs": {"values": [3, 4, 5]},
                }
            ],
        )
    )
    store.save(old_run)
    store.save(recent_run)
    with sqlite3.connect(str(tmp_path / "scheduled-retention.sqlite3")) as connection:
        connection.execute(
            "UPDATE lab_runs SET created_at = ? WHERE run_id = ?",
            ("2020-01-01T00:00:00+00:00", str(old_run.run_id)),
        )

    deleted_count = run_retention(
        store,
        30,
        now=datetime(2026, 10, 26, tzinfo=UTC),
    )

    assert deleted_count == 1
    with pytest.raises(LabRunNotFound):
        store.get(old_run.run_id)
    assert store.get(recent_run.run_id).run_id == recent_run.run_id
    with sqlite3.connect(str(tmp_path / "scheduled-retention.sqlite3")) as connection:
        tombstone = connection.execute(
            "SELECT reason FROM lab_run_retention_events WHERE run_id = ?",
            (str(old_run.run_id),),
        ).fetchone()
    assert tombstone == ("scheduled_retention_30_days",)


def test_opt_in_retention_job_validates_days_and_timezone(tmp_path) -> None:
    from datetime import datetime

    from artificial_scientist.lab.retention import run_retention

    store = LabRunStore(str(tmp_path / "retention-validation.sqlite3"))
    with pytest.raises(ValueError, match="between 1 and"):
        run_retention(store, 0)
    with pytest.raises(ValueError, match="timezone"):
        run_retention(store, 30, now=datetime(2026, 10, 26))



def test_binary_artifact_upload_download_and_provenance(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "binary-artifact-api.sqlite3"))
    app.dependency_overrides[get_lab_store] = lambda: store
    client = TestClient(app)
    try:
        created = client.post(
            "/api/v1/lab/runs",
            json={
                "title": "Binary attachment test",
                "steps": [
                    {
                        "step_id": "stats",
                        "operation": "statistics",
                        "inputs": {"values": [2, 4, 6]},
                    }
                ],
            },
        )
        assert created.status_code == 201
        run_id = created.json()["run_id"]
        payload = b"ASDS scientific attachment\x00\x01\xff"
        uploaded = client.post(
            f"/api/v1/lab/runs/{run_id}/binary-artifacts?filename=measurement.bin",
            content=payload,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert uploaded.status_code == 201
        metadata = uploaded.json()
        assert metadata["filename"] == "measurement.bin"
        assert metadata["size_bytes"] == len(payload)
        assert metadata["sha256"] == hashlib.sha256(payload).hexdigest()
        assert metadata["provenance"]["run_id"] == run_id
        assert metadata["provenance"]["malware_scan"]["status"] == metadata["scan_status"]
        assert metadata["provenance"]["malware_scan"]["recorded_at"]
        if metadata["scan_status"] == "skipped_development":
            assert metadata["provenance"]["malware_scan"]["scanner"] is None

        listing = client.get(f"/api/v1/lab/runs/{run_id}/binary-artifacts")
        assert listing.status_code == 200
        assert listing.json()[0]["artifact_id"] == metadata["artifact_id"]

        downloaded = client.get(f"/api/v1/lab/binary-artifacts/{metadata['artifact_id']}")
        assert downloaded.status_code == 200
        assert downloaded.content == payload
        assert downloaded.headers["x-content-sha256"] == metadata["sha256"]
        assert downloaded.headers["x-content-type-options"] == "nosniff"
    finally:
        app.dependency_overrides.pop(get_lab_store, None)


def test_binary_artifact_upload_rejects_unsafe_filename_and_empty_content(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "binary-artifact-validation.sqlite3"))
    app.dependency_overrides[get_lab_store] = lambda: store
    client = TestClient(app)
    try:
        created = client.post(
            "/api/v1/lab/runs",
            json={
                "title": "Binary attachment validation",
                "steps": [
                    {
                        "step_id": "stats",
                        "operation": "statistics",
                        "inputs": {"values": [1, 2, 3]},
                    }
                ],
            },
        )
        assert created.status_code == 201
        run_id = created.json()["run_id"]
        unsafe = client.post(
            f"/api/v1/lab/runs/{run_id}/binary-artifacts?filename=..%2Fsecret.bin",
            content=b"not allowed",
            headers={"Content-Type": "application/octet-stream"},
        )
        assert unsafe.status_code == 422
        empty = client.post(
            f"/api/v1/lab/runs/{run_id}/binary-artifacts?filename=empty.bin",
            content=b"",
            headers={"Content-Type": "application/octet-stream"},
        )
        assert empty.status_code == 422
    finally:
        app.dependency_overrides.pop(get_lab_store, None)



def test_binary_artifact_quotas_are_enforced_per_run(tmp_path, monkeypatch) -> None:
    store = LabRunStore(str(tmp_path / "binary-artifact-quota.sqlite3"))
    run = run_lab(
        LabRunRequest(
            title="Quota enforcement",
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
    monkeypatch.setattr(lab_store_module, "_MAX_BINARY_ARTIFACTS_PER_RUN", 3)
    monkeypatch.setattr(lab_store_module, "_MAX_BINARY_BYTES_PER_RUN", 5)

    first = store.save_binary_artifact(
        run.run_id, "first.bin", "application/octet-stream", b"abc"
    )
    second = store.save_binary_artifact(
        run.run_id, "second.bin", "application/octet-stream", b"de"
    )
    assert first["size_bytes"] == 3
    assert second["size_bytes"] == 2

    with pytest.raises(ValueError, match="storage quota"):
        store.save_binary_artifact(
            run.run_id, "third.bin", "application/octet-stream", b"x"
        )

    # Repeating an identical upload is idempotent and does not consume quota twice.
    duplicate = store.save_binary_artifact(
        run.run_id, "first.bin", "application/octet-stream", b"abc"
    )
    assert duplicate["artifact_id"] == first["artifact_id"]

    monkeypatch.setattr(lab_store_module, "_MAX_BINARY_ARTIFACTS_PER_RUN", 2)
    monkeypatch.setattr(lab_store_module, "_MAX_BINARY_BYTES_PER_RUN", 100)
    with pytest.raises(ValueError, match="count quota"):
        store.save_binary_artifact(
            run.run_id, "fourth.bin", "application/octet-stream", b"x"
        )

    other_run = run_lab(
        LabRunRequest(
            title="Independent quota",
            steps=[
                {
                    "step_id": "stats",
                    "operation": "statistics",
                    "inputs": {"values": [4, 5, 6]},
                }
            ],
        )
    )
    store.save(other_run)
    independent = store.save_binary_artifact(
        other_run.run_id, "fresh.bin", "application/octet-stream", b"12345"
    )
    assert independent["size_bytes"] == 5



def test_interrupted_execution_attempts_are_recovered_and_auditable(tmp_path) -> None:
    database = str(tmp_path / "execution-recovery.sqlite3")
    store = LabRunStore(database)
    request = LabRunRequest(
        title="Recover interrupted execution",
        steps=[
            {
                "step_id": "stats",
                "operation": "statistics",
                "inputs": {"values": [1, 2, 3]},
            }
        ],
    )

    interrupted_id = uuid4()
    store.begin_execution(interrupted_id, request)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE lab_execution_attempts
            SET started_at = ?, updated_at = ?
            WHERE run_id = ?
            """,
            (
                "2020-01-01T00:00:00+00:00",
                "2020-01-01T00:00:00+00:00",
                str(interrupted_id),
            ),
        )
    restarted_store = LabRunStore(database)
    interrupted = restarted_store.get_execution_status(interrupted_id)
    assert interrupted["status"] == "interrupted"
    assert interrupted["finished_at"] is not None
    assert "Process stopped" in interrupted["failure_reason"]

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE lab_execution_attempts SET started_at = ? WHERE run_id = ?",
            ("2020-01-01T00:00:00+00:00", str(interrupted_id)),
        )
    assert restarted_store.purge_runs_before("2021-01-01T00:00:00+00:00") == []
    with sqlite3.connect(database) as connection:
        redacted_request = connection.execute(
            "SELECT request_json FROM lab_execution_attempts WHERE run_id = ?",
            (str(interrupted_id),),
        ).fetchone()[0]
    assert redacted_request == "{}"

    app.dependency_overrides[get_lab_store] = lambda: restarted_store
    try:
        status_response = TestClient(app).get(
            f"/api/v1/lab/runs/{interrupted_id}/execution-status"
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "interrupted"
    finally:
        app.dependency_overrides.pop(get_lab_store, None)

    active_id = uuid4()
    store.begin_execution(active_id, request)
    active_store = LabRunStore(database)
    assert active_store.get_execution_status(active_id)["status"] == "running"
    store.fail_execution(active_id)

    completed_id = uuid4()
    store.begin_execution(completed_id, request)
    run = run_lab(request, run_id=completed_id)
    store.save(run)
    completed = store.get_execution_status(completed_id)
    assert completed["status"] == "completed"
    assert completed["result_sha256"] == run.result_sha256

    # Reconcile a stale status when the durable run record already exists.
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE lab_execution_attempts
            SET status = 'running', updated_at = '2020-01-01T00:00:00+00:00',
                finished_at = NULL, result_sha256 = NULL
            WHERE run_id = ?
            """,
            (str(completed_id),),
        )
        connection.commit()
    reconciled_store = LabRunStore(database)
    reconciled = reconciled_store.get_execution_status(completed_id)
    assert reconciled["status"] == "completed"
    assert reconciled["result_sha256"] == run.result_sha256

    with pytest.raises(LabExecutionNotFound):
        store.get_execution_status(uuid4())



def test_clamav_scanner_fails_closed_outside_development(monkeypatch) -> None:
    monkeypatch.delenv("ARTIFICIAL_SCIENTIST_CLAMAV_HOST", raising=False)
    with pytest.raises(lab_scanning.ScannerUnavailable):
        lab_scanning.scan_binary_content(b"evidence", environment="production")
    assert (
        lab_scanning.scan_binary_content(b"evidence", environment="development")
        == "skipped_development"
    )


def test_clamav_scanner_sends_instream_and_accepts_clean_result(monkeypatch) -> None:
    sent: list[bytes] = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            return None

        def sendall(self, data):
            sent.append(data)

        def recv(self, _size):
            return b"stream: OK\0"

    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_CLAMAV_HOST", "scanner.internal")
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_CLAMAV_PORT", "3310")
    monkeypatch.setattr(
        lab_scanning.socket,
        "create_connection",
        lambda *_args, **_kwargs: FakeConnection(),
    )
    assert lab_scanning.scan_binary_content(b"clean sample", environment="production") == "clean"
    assert sent[0] == b"zINSTREAM\0"
    assert sent[1] == len(b"clean sample").to_bytes(4, "big") + b"clean sample"
    assert sent[2] == b"\0\0\0\0"



def test_clamav_scanner_rejects_incomplete_success_response(monkeypatch) -> None:
    class TruncatedConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            return None

        def sendall(self, _data):
            return None

        def recv(self, _size):
            return b"stream: OK"

    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_CLAMAV_HOST", "scanner.internal")
    monkeypatch.setattr(
        lab_scanning.socket,
        "create_connection",
        lambda *_args, **_kwargs: TruncatedConnection(),
    )
    with pytest.raises(lab_scanning.ScannerUnavailable, match="incomplete response"):
        lab_scanning.scan_binary_content(b"test sample", environment="production")


def test_clamav_scanner_rejects_detected_malware(monkeypatch) -> None:
    class InfectedConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            return None

        def sendall(self, _data):
            return None

        def recv(self, _size):
            return b"stream: Eicar-Test-Signature FOUND\0"

    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_CLAMAV_HOST", "scanner.internal")
    monkeypatch.setattr(
        lab_scanning.socket,
        "create_connection",
        lambda *_args, **_kwargs: InfectedConnection(),
    )
    with pytest.raises(lab_scanning.MalwareDetected):
        lab_scanning.scan_binary_content(b"test sample", environment="production")


def test_clamav_scanner_rejects_invalid_utf8_response(monkeypatch) -> None:
    class InvalidEncodingConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            return None

        def sendall(self, _data):
            return None

        def recv(self, _size):
            return b"stream: " + bytes([0xFF]) + b" OK\0"

    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_CLAMAV_HOST", "scanner.internal")
    monkeypatch.setattr(
        lab_scanning.socket,
        "create_connection",
        lambda *_args, **_kwargs: InvalidEncodingConnection(),
    )
    with pytest.raises(lab_scanning.ScannerUnavailable, match="invalid response"):
        lab_scanning.scan_binary_content(b"test sample", environment="production")
