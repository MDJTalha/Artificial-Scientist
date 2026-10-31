"""Migration/recovery fixture integrity and rollback assertions."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from uuid import uuid4

from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabRunStore
from artificial_scientist.phase6_rehearsal import rehearse_legacy_claims


def _request() -> LabRunRequest:
    return LabRunRequest(
        title="migration-fixture",
        steps=[
            {
                "step_id": "summary",
                "operation": "statistics",
                "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
            }
        ],
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_rehearsal_preserves_source_byte_identity_and_reopenability(tmp_path):
    database = tmp_path / "source.sqlite3"
    directory = TenantDirectory(str(database))
    operator = directory.register_principal("https://issuer.example/", "operator")
    tenant = directory.create_tenant("migration-target", "Migration Target")
    store = LabRunStore(str(database))
    run = run_lab(_request())
    store.save(run)

    before = _digest(database)
    result = rehearse_legacy_claims(
        str(database),
        [{"run_id": str(run.run_id), "tenant_id": tenant}],
        operator_principal_id=operator,
    )

    assert result["source_database_modified"] is False
    assert _digest(database) == before

    reopened = LabRunStore(str(database))
    assert reopened.get(run.run_id).run_id == run.run_id
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT tenant_id FROM lab_runs WHERE run_id = ?", (str(run.run_id),)
        ).fetchone()[0] is None


def test_failed_rehearsal_leaves_source_and_no_partial_claim(tmp_path):
    database = tmp_path / "rollback.sqlite3"
    directory = TenantDirectory(str(database))
    operator = directory.register_principal("https://issuer.example/", "operator")
    tenant = directory.create_tenant("rollback-target", "Rollback Target")
    store = LabRunStore(str(database))
    run = run_lab(_request())
    store.save(run)
    before = _digest(database)

    try:
        rehearse_legacy_claims(
            str(database),
            [
                {"run_id": str(run.run_id), "tenant_id": tenant},
                {"run_id": str(uuid4()), "tenant_id": tenant},
            ],
            operator_principal_id=operator,
        )
    except Exception:
        pass
    else:
        raise AssertionError("fixture must exercise a failed rehearsal")

    assert _digest(database) == before
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT tenant_id FROM lab_runs WHERE run_id = ?", (str(run.run_id),)
        ).fetchone()[0] is None
        assert connection.execute(
            "SELECT COUNT(*) FROM asds_security_audit WHERE action = 'legacy:claim'"
        ).fetchone()[0] == 0
