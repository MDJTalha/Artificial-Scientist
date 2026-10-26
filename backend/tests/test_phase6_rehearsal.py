"""Tests for the Phase 6 migration rehearsal safety wrapper."""

import sqlite3
from uuid import uuid4

import pytest

from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabRunNotFound, LabRunStore
from artificial_scientist.legacy_claim import LegacyClaimError
from artificial_scientist.phase6_rehearsal import rehearse_legacy_claims


def _request() -> LabRunRequest:
    return LabRunRequest(
        title="Phase 6 rehearsal fixture",
        steps=[
            {
                "step_id": "summary",
                "operation": "statistics",
                "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
            }
        ],
    )


def test_rehearsal_verifies_claims_without_modifying_source_database(tmp_path):
    database = str(tmp_path / "phase6-source.sqlite3")
    directory = TenantDirectory(database)
    operator_id = directory.register_principal("https://issuer.example/", "operator")
    tenant_id = directory.create_tenant("rehearsal-target", "Rehearsal Target")
    store = LabRunStore(database)
    run_id = uuid4()
    store.begin_execution(run_id, _request())
    store.save(run_lab(_request(), run_id=run_id))
    claims = [{"run_id": str(run_id), "tenant_id": tenant_id}]

    result = rehearse_legacy_claims(
        database, claims, operator_principal_id=operator_id
    )

    assert result == {
        "mode": "rehearsal",
        "source_database_modified": False,
        "claims_checked": 1,
        "claims_that_needed_updates": 1,
        "claims_applied_on_temporary_snapshot": 1,
        "ownership_verified": True,
        "operator_audit_verified": True,
    }
    assert store.get(run_id).run_id == run_id
    with pytest.raises(LabRunNotFound):
        store.get(run_id, tenant_id=tenant_id)
    assert directory.list_audit_events(tenant_id) == []


def test_rehearsal_rejects_missing_source_database(tmp_path):
    with pytest.raises(LegacyClaimError, match="existing on-disk database"):
        rehearse_legacy_claims(
            str(tmp_path / "missing.sqlite3"),
            [{"run_id": str(uuid4()), "tenant_id": str(uuid4())}],
            operator_principal_id=str(uuid4()),
        )


def test_rehearsal_rejects_missing_operator(tmp_path):
    database = str(tmp_path / "phase6-operator.sqlite3")
    directory = TenantDirectory(database)
    tenant_id = directory.create_tenant("rehearsal-operator", "Rehearsal Operator")
    store = LabRunStore(database)
    run = run_lab(_request())
    store.save(run)

    with pytest.raises(LegacyClaimError, match="does not exist in the tenant directory"):
        rehearse_legacy_claims(
            database,
            [{"run_id": str(run.run_id), "tenant_id": tenant_id}],
            operator_principal_id=str(uuid4()),
        )

    assert store.get(run.run_id).run_id == run.run_id
    with sqlite3.connect(database) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM asds_security_audit WHERE action = 'legacy:claim'"
        ).fetchone()[0]
    assert count == 0
