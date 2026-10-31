"""Cross-tenant denial tests for binary lab attachments."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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

def test_tenant_wide_binary_count_quota_is_enforced_across_runs(
    tmp_path, monkeypatch
) -> None:
    import artificial_scientist.lab.store as store_module

    monkeypatch.setattr(store_module, "_MAX_BINARY_ARTIFACTS_PER_TENANT", 1)
    store = LabRunStore(str(tmp_path / "tenant-binary-quota.sqlite3"))
    run_a = _run()
    run_b = _run()
    store.save(run_a, tenant_id="tenant-a")
    store.save(run_b, tenant_id="tenant-a")

    store.save_binary_artifact(
        run_a.run_id,
        "first.bin",
        "application/octet-stream",
        b"first",
        scan_status="clean",
        tenant_id="tenant-a",
    )
    with pytest.raises(ValueError, match="Tenant has reached its binary artifact count quota"):
        store.save_binary_artifact(
            run_b.run_id,
            "second.bin",
            "application/octet-stream",
            b"second",
            scan_status="clean",
            tenant_id="tenant-a",
        )

    # A separate tenant has an independent quota and its own run ownership.
    run_c = _run()
    store.save(run_c, tenant_id="tenant-b")
    store.save_binary_artifact(
        run_c.run_id,
        "other-tenant.bin",
        "application/octet-stream",
        b"third",
        scan_status="clean",
        tenant_id="tenant-b",
    )


def test_tenant_wide_binary_byte_quota_is_enforced_across_runs(
    tmp_path, monkeypatch
) -> None:
    import artificial_scientist.lab.store as store_module

    monkeypatch.setattr(store_module, "_MAX_BINARY_BYTES_PER_TENANT", 5)
    store = LabRunStore(str(tmp_path / "tenant-binary-byte-quota.sqlite3"))
    run_a = _run()
    run_b = _run()
    store.save(run_a, tenant_id="tenant-a")
    store.save(run_b, tenant_id="tenant-a")
    store.save_binary_artifact(
        run_a.run_id,
        "first.bin",
        "application/octet-stream",
        b"12345",
        scan_status="clean",
        tenant_id="tenant-a",
    )

    with pytest.raises(ValueError, match="Tenant has reached its binary artifact storage quota"):
        store.save_binary_artifact(
            run_b.run_id,
            "second.bin",
            "application/octet-stream",
            b"x",
            scan_status="clean",
            tenant_id="tenant-a",
        )




def test_concurrent_binary_uploads_cannot_oversubscribe_tenant_count_quota(
    tmp_path, monkeypatch
) -> None:
    import artificial_scientist.lab.store as store_module

    quota = 2
    workers = 6
    monkeypatch.setattr(store_module, "_MAX_BINARY_ARTIFACTS_PER_TENANT", quota)
    store = LabRunStore(str(tmp_path / "binary-quota-concurrency.sqlite3"))
    runs = [_run() for _ in range(workers)]
    for run in runs:
        store.save(run, tenant_id="tenant-concurrent")
    barrier = Barrier(workers)

    def attach(index: int) -> bool:
        barrier.wait(timeout=5)
        try:
            store.save_binary_artifact(
                runs[index].run_id,
                f"parallel-{index}.bin",
                "application/octet-stream",
                f"payload-{index}".encode(),
                scan_status="skipped_development",
                tenant_id="tenant-concurrent",
            )
        except ValueError as exc:
            if "Tenant has reached its binary artifact count quota" not in str(exc):
                raise
            return False
        return True

    with ThreadPoolExecutor(max_workers=workers) as executor:
        outcomes = list(executor.map(attach, range(workers)))

    assert sum(outcomes) == quota
    persisted_count = sum(
        len(store.list_binary_artifacts(run.run_id, tenant_id="tenant-concurrent"))
        for run in runs
    )
    assert persisted_count == quota
