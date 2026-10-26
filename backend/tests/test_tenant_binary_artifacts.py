"""Cross-tenant denial tests for binary lab attachments."""

import pytest

from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabArtifactNotFound, LabRunNotFound, LabRunStore


def _run():
    return run_lab(
        LabRunRequest(
            title="Binary attachment tenant test",
            steps=[
                {
                    "step_id": "summary",
                    "operation": "statistics",
                    "inputs": {"values": [3, 6, 9], "variance_mode": "population"},
                }
            ],
        )
    )


def test_binary_artifact_read_and_list_are_tenant_scoped(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "binary-tenant.sqlite3"))
    run = _run()
    store.save(run, tenant_id="tenant-a")
    artifact = store.save_binary_artifact(
        run.run_id,
        "result.bin",
        "application/octet-stream",
        b"validated attachment",
        scan_status="skipped_development",
        tenant_id="tenant-a",
    )

    assert len(store.list_binary_artifacts(run.run_id, tenant_id="tenant-a")) == 1
    assert store.get_binary_artifact(
        __import__("uuid").UUID(artifact["artifact_id"]), tenant_id="tenant-a"
    )["content"] == b"validated attachment"

    with pytest.raises(LabRunNotFound):
        store.list_binary_artifacts(run.run_id, tenant_id="tenant-b")
    with pytest.raises(LabArtifactNotFound):
        store.get_binary_artifact(
            __import__("uuid").UUID(artifact["artifact_id"]), tenant_id="tenant-b"
        )

def test_unowned_legacy_binary_artifact_is_not_visible_to_tenant(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "binary-legacy-tenant.sqlite3"))
    legacy_run = _run()
    store.save(legacy_run)
    artifact = store.save_binary_artifact(
        legacy_run.run_id,
        "legacy.bin",
        "application/octet-stream",
        b"legacy attachment",
        scan_status="skipped_development",
    )

    with pytest.raises(LabRunNotFound):
        store.list_binary_artifacts(legacy_run.run_id, tenant_id="tenant-a")
    with pytest.raises(LabArtifactNotFound):
        store.get_binary_artifact(
            __import__("uuid").UUID(artifact["artifact_id"]), tenant_id="tenant-a"
        )

