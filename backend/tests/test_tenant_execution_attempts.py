"""Adversarial tenant-isolation tests for durable execution-attempt records."""

from uuid import uuid4

import pytest

from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabExecutionNotFound, LabRunStore


def _request() -> LabRunRequest:
    return LabRunRequest(
        title="Execution ownership regression",
        steps=[
            {
                "step_id": "summary",
                "operation": "statistics",
                "inputs": {"values": [2, 4, 6], "variance_mode": "population"},
            }
        ],
    )


def test_execution_status_is_visible_only_to_owning_tenant(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "execution-tenant.sqlite3"))
    run_id = uuid4()

    created = store.begin_execution(run_id, _request(), tenant_id="tenant-a")
    assert created["run_id"] == str(run_id)
    assert created["status"] == "running"
    assert store.get_execution_status(run_id, tenant_id="tenant-a")["status"] == "running"

    with pytest.raises(LabExecutionNotFound):
        store.get_execution_status(run_id, tenant_id="tenant-b")


def test_execution_status_does_not_expose_unowned_legacy_attempt_to_tenant(
    tmp_path,
) -> None:
    store = LabRunStore(str(tmp_path / "execution-legacy.sqlite3"))
    run_id = uuid4()

    store.begin_execution(run_id, _request())

    with pytest.raises(LabExecutionNotFound):
        store.get_execution_status(run_id, tenant_id="tenant-a")


def test_execution_status_for_unknown_id_is_not_found_for_tenant(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "execution-missing.sqlite3"))

    with pytest.raises(LabExecutionNotFound):
        store.get_execution_status(uuid4(), tenant_id="tenant-a")


def test_failure_update_cannot_mutate_another_tenants_attempt(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "execution-failure-tenant.sqlite3"))
    run_id = uuid4()
    store.begin_execution(run_id, _request(), tenant_id="tenant-a")

    store.fail_execution(run_id, tenant_id="tenant-b")

    assert store.get_execution_status(run_id, tenant_id="tenant-a")["status"] == "running"
    store.fail_execution(run_id, tenant_id="tenant-a")
    assert store.get_execution_status(run_id, tenant_id="tenant-a")["status"] == "failed"
