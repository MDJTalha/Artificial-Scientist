"""Adversarial tenant-isolation tests for durable execution-attempt records."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
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


def test_tenant_failure_update_cannot_mutate_unowned_legacy_attempt(tmp_path) -> None:
    store = LabRunStore(str(tmp_path / "execution-legacy-failure.sqlite3"))
    run_id = uuid4()
    store.begin_execution(run_id, _request())

    store.fail_execution(run_id, tenant_id="tenant-a")

    # The legacy attempt remains unmodified; tenant-scoped mutation must not
    # silently fall back to an unowned record.
    assert store.get_execution_status(run_id)["status"] == "running"
    with pytest.raises(LabExecutionNotFound):
        store.get_execution_status(run_id, tenant_id="tenant-a")


def test_tenant_wide_lab_run_quota_is_enforced_atomically(tmp_path, monkeypatch) -> None:
    import artificial_scientist.lab.store as store_module

    monkeypatch.setattr(store_module, "_MAX_RUNS_PER_TENANT", 1)
    store = LabRunStore(str(tmp_path / "execution-tenant-quota.sqlite3"))
    store.begin_execution(uuid4(), _request(), tenant_id="tenant-a")

    with pytest.raises(ValueError, match="Tenant has reached its lab run quota"):
        store.begin_execution(uuid4(), _request(), tenant_id="tenant-a")

    # The cap is tenant-specific, not a global service-wide limit.
    other_tenant = store.begin_execution(uuid4(), _request(), tenant_id="tenant-b")
    assert other_tenant["status"] == "running"




def test_concurrent_run_creation_cannot_oversubscribe_tenant_quota(
    tmp_path, monkeypatch
) -> None:
    import artificial_scientist.lab.store as store_module

    quota = 3
    workers = 8
    monkeypatch.setattr(store_module, "_MAX_RUNS_PER_TENANT", quota)
    store = LabRunStore(str(tmp_path / "execution-tenant-concurrency.sqlite3"))
    barrier = Barrier(workers)

    def attempt(index: int) -> bool:
        barrier.wait(timeout=5)
        try:
            store.begin_execution(
                uuid4(),
                _request(),
                tenant_id="tenant-concurrent",
            )
        except ValueError as exc:
            if "Tenant has reached its lab run quota" not in str(exc):
                raise
            return False
        return True

    with ThreadPoolExecutor(max_workers=workers) as executor:
        outcomes = list(executor.map(attempt, range(workers)))

    assert sum(outcomes) == quota
    import sqlite3

    with sqlite3.connect(store.database_path) as connection:
        persisted_attempts = connection.execute(
            "SELECT COUNT(*) FROM lab_execution_attempts WHERE tenant_id = ?",
            ("tenant-concurrent",),
        ).fetchone()[0]
    assert persisted_attempts == quota


def test_retention_purge_releases_tenant_run_quota(tmp_path, monkeypatch) -> None:
    from artificial_scientist.lab.engine import run_lab
    import artificial_scientist.lab.store as store_module

    monkeypatch.setattr(store_module, "_MAX_RUNS_PER_TENANT", 1)
    store = LabRunStore(str(tmp_path / "execution-retention-quota.sqlite3"))
    tenant_id = "tenant-retention"
    first_run_id = uuid4()
    store.begin_execution(first_run_id, _request(), tenant_id=tenant_id)
    store.save(run_lab(_request(), run_id=first_run_id), tenant_id=tenant_id)

    assert store.purge_runs_before("9999-12-31T23:59:59+00:00") == [str(first_run_id)]

    # The retained tombstone preserves evidence, but a purged run no longer consumes
    # the tenant's live run quota.
    second = store.begin_execution(uuid4(), _request(), tenant_id=tenant_id)
    assert second["status"] == "running"
