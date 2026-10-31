"""Concurrency regressions for tenant quota and execution ownership."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import artificial_scientist.lab.store as store_module
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabQuotaExceeded, LabRunStore


def _request() -> LabRunRequest:
    return LabRunRequest(
        title="quota-race",
        steps=[
            {
                "step_id": "summary",
                "operation": "statistics",
                "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
            }
        ],
    )


def test_run_quota_is_atomic_under_concurrent_reservations(tmp_path, monkeypatch):
    database = str(tmp_path / "quota-race.sqlite3")
    monkeypatch.setattr(store_module, "_MAX_RUNS_PER_TENANT", 1)
    store = LabRunStore(database)
    tenant = "tenant-race"

    def reserve(_: int) -> str:
        try:
            store.begin_execution(uuid4(), _request(), tenant_id=tenant)
            return "accepted"
        except LabQuotaExceeded:
            return "rejected"

    with ThreadPoolExecutor(max_workers=12) as pool:
        outcomes = list(pool.map(reserve, range(48)))

    assert outcomes.count("accepted") == 1
    assert outcomes.count("rejected") == 47
    _, total = store.list_runs(tenant_id=tenant)
    assert total == 0


def test_same_run_id_cannot_be_reassigned_across_tenants(tmp_path):
    database = str(tmp_path / "ownership-race.sqlite3")
    store = LabRunStore(database)
    run_id = uuid4()

    def reserve(tenant: str) -> str:
        try:
            store.begin_execution(run_id, _request(), tenant_id=tenant)
            return "accepted"
        except Exception as error:  # sqlite uniqueness is the intended loser path
            return type(error).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, ("tenant-a", "tenant-b")))

    assert outcomes.count("accepted") == 1
    store.get_execution_status(run_id)
    tenant_rows = []
    with store._connect() as connection:
        tenant_rows = [
            row["tenant_id"]
            for row in connection.execute(
                "SELECT tenant_id FROM lab_execution_attempts WHERE run_id = ?",
                (str(run_id),),
            )
        ]
    assert len(tenant_rows) == 1
    assert tenant_rows[0] in {"tenant-a", "tenant-b"}
