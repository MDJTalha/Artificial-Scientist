"""Regression tests for tenant-scoped controlled-lab persistence."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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


def test_tenant_wide_json_artifact_count_quota_is_enforced_across_runs(
    tmp_path, monkeypatch
) -> None:
    import artificial_scientist.lab.store as store_module

    store = LabRunStore(str(tmp_path / "tenant-json-count-quota.sqlite3"))
    monkeypatch.setattr(store_module, "_MAX_JSON_ARTIFACTS_PER_TENANT", 1)

    store.save(_run("Tenant A first"), tenant_id="tenant-a")
    with pytest.raises(ValueError, match="JSON artifact count quota"):
        store.save(_run("Tenant A second"), tenant_id="tenant-a")

    # Quotas are isolated: a different tenant can still use its own budget.
    store.save(_run("Tenant B first"), tenant_id="tenant-b")


def test_tenant_wide_json_artifact_byte_quota_is_enforced(
    tmp_path, monkeypatch
) -> None:
    import sqlite3

    import artificial_scientist.lab.store as store_module

    database = str(tmp_path / "tenant-json-byte-quota.sqlite3")
    store = LabRunStore(database)
    first = _run("Tenant A first")
    store.save(first, tenant_id="tenant-a")

    with sqlite3.connect(database) as connection:
        used_bytes = connection.execute(
            """
            SELECT COALESCE(SUM(artifacts.size_bytes), 0)
            FROM lab_artifacts AS artifacts
            JOIN lab_runs AS runs ON runs.run_id = artifacts.run_id
            WHERE runs.tenant_id = ?
            """,
            ("tenant-a",),
        ).fetchone()[0]
    monkeypatch.setattr(store_module, "_MAX_JSON_BYTES_PER_TENANT", used_bytes + 1)

    with pytest.raises(ValueError, match="JSON artifact storage quota"):
        store.save(_run("Tenant A second"), tenant_id="tenant-a")

    store.save(_run("Tenant B first"), tenant_id="tenant-b")



def test_legacy_database_schema_migrates_without_assigning_tenant_ownership(tmp_path) -> None:
    import json
    import sqlite3

    database = str(tmp_path / "legacy-schema.sqlite3")
    legacy_run = _run("Pre-tenant schema record")
    payload = json.dumps(
        legacy_run.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )

    # Simulate the previous schema before tenant_id was introduced.
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE lab_runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
                configuration_sha256 TEXT NOT NULL,
                result_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO lab_runs (
                run_id, status, configuration_sha256, result_sha256,
                created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(legacy_run.run_id),
                legacy_run.status,
                legacy_run.configuration_sha256,
                legacy_run.result_sha256,
                legacy_run.started_at,
                payload,
            ),
        )

    # Initialization performs the additive migration but must not infer an owner.
    store = LabRunStore(database)
    assert store.get(legacy_run.run_id).title == "Pre-tenant schema record"
    with pytest.raises(LabRunNotFound):
        store.get(legacy_run.run_id, tenant_id="tenant-a")

    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(lab_runs)")
        }
        owner = connection.execute(
            "SELECT tenant_id FROM lab_runs WHERE run_id = ?",
            (str(legacy_run.run_id),),
        ).fetchone()[0]
    assert "tenant_id" in columns
    assert owner is None



def test_concurrent_run_saves_cannot_oversubscribe_tenant_json_artifact_quota(
    tmp_path, monkeypatch
) -> None:
    import artificial_scientist.lab.store as store_module

    quota = 2
    workers = 6
    store = LabRunStore(str(tmp_path / "json-quota-concurrency.sqlite3"))
    store.save(_run("Tenant existing run"), tenant_id="tenant-concurrent")
    monkeypatch.setattr(store_module, "_MAX_JSON_ARTIFACTS_PER_TENANT", quota)
    candidates = [_run(f"Concurrent run {index}") for index in range(workers)]
    barrier = Barrier(workers)

    def persist(index: int) -> bool:
        barrier.wait(timeout=5)
        try:
            store.save(candidates[index], tenant_id="tenant-concurrent")
        except ValueError as exc:
            if "JSON artifact count quota" not in str(exc):
                raise
            return False
        return True

    with ThreadPoolExecutor(max_workers=workers) as executor:
        outcomes = list(executor.map(persist, range(workers)))

    assert sum(outcomes) == quota - 1
    runs, total = store.list_runs(tenant_id="tenant-concurrent")
    assert total == quota
    assert len(runs) == quota
    assert len(store.list_artifacts(runs[0].run_id, tenant_id="tenant-concurrent")) == 1
    with store._connect() as connection:
        artifact_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM lab_artifacts AS artifacts
            JOIN lab_runs AS runs ON runs.run_id = artifacts.run_id
            WHERE runs.tenant_id = ?
            """,
            ("tenant-concurrent",),
        ).fetchone()[0]
    assert artifact_count == quota
