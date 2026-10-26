"""Regression tests for tenant-scoped controlled-lab persistence."""

import pytest

from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabArtifactNotFound, LabRunNotFound, LabRunStore


def _run(title: str):
    return run_lab(
        LabRunRequest(
            title=title,
            steps=[
                {
                    "step_id": "summary",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
                }
            ],
        )
    )


def test_tenant_scope_is_enforced_for_run_lists_reads_and_json_artifacts(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "tenant-scope.sqlite3"))
    tenant_a = "tenant-a"
    tenant_b = "tenant-b"
    run_a = _run("Tenant A")
    run_b = _run("Tenant B")
    store.save(run_a, tenant_id=tenant_a)
    store.save(run_b, tenant_id=tenant_b)

    runs_a, total_a = store.list_runs(tenant_id=tenant_a)
    assert total_a == 1
    assert [run.run_id for run in runs_a] == [run_a.run_id]
    assert store.get(run_a.run_id, tenant_id=tenant_a).title == "Tenant A"

    with pytest.raises(LabRunNotFound):
        store.get(run_a.run_id, tenant_id=tenant_b)

    artifacts_a = store.list_artifacts(run_a.run_id, tenant_id=tenant_a)
    assert len(artifacts_a) == 1
    assert store.get_artifact(artifacts_a[0].artifact_id, tenant_id=tenant_a).content[
        "title"
    ] == "Tenant A"

    with pytest.raises(LabRunNotFound):
        store.list_artifacts(run_a.run_id, tenant_id=tenant_b)
    with pytest.raises(LabArtifactNotFound):
        store.get_artifact(artifacts_a[0].artifact_id, tenant_id=tenant_b)


def test_tenant_scoped_lists_do_not_include_unowned_legacy_runs(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "tenant-legacy.sqlite3"))
    legacy_run = _run("Legacy unowned")
    tenant_run = _run("Owned")
    store.save(legacy_run)
    store.save(tenant_run, tenant_id="tenant-a")

    runs, total = store.list_runs(tenant_id="tenant-a")
    assert total == 1
    assert [run.run_id for run in runs] == [tenant_run.run_id]

    with pytest.raises(LabRunNotFound):
        store.get(legacy_run.run_id, tenant_id="tenant-a")
