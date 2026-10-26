"""Tests for the explicit legacy ownership claim workflow."""

import pytest
from uuid import uuid4

from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabRunNotFound, LabRunStore
from artificial_scientist.legacy_claim import LegacyClaimError, claim_legacy_runs


def _request() -> LabRunRequest:
    return LabRunRequest(
        title="Legacy claim fixture",
        steps=[
            {
                "step_id": "summary",
                "operation": "statistics",
                "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
            }
        ],
    )


def test_legacy_claim_defaults_to_dry_run_then_updates_atomically(tmp_path):
    database = str(tmp_path / "legacy-claim.sqlite3")
    directory = TenantDirectory(database)
    operator_id = directory.register_principal("https://issuer.example/", "operator")
    tenant_id = directory.create_tenant("claim-target", "Claim Target")
    store = LabRunStore(database)
    run_id = uuid4()
    store.begin_execution(run_id, _request())
    run = run_lab(_request(), run_id=run_id)
    store.save(run)
    claims = [{"run_id": str(run_id), "tenant_id": tenant_id}]

    dry_run = claim_legacy_runs(database, claims)
    assert dry_run["mode"] == "dry-run"
    assert dry_run["claims_to_update"] == 1
    assert store.get(run_id).run_id == run_id
    with pytest.raises(LabRunNotFound):
        store.get(run_id, tenant_id=tenant_id)

    applied = claim_legacy_runs(
        database,
        claims,
        apply=True,
        operator_principal_id=operator_id,
    )
    assert applied["mode"] == "apply"
    assert store.get(run_id, tenant_id=tenant_id).run_id == run_id
    assert store.get_execution_status(run_id, tenant_id=tenant_id)["status"] == "completed"
    events = directory.list_audit_events(tenant_id)
    assert len(events) == 1
    assert events[0]["action"] == "legacy:claim"
    assert events[0]["principal_id"] == operator_id
    assert events[0]["target_id"] == str(run_id)


def test_legacy_claim_rejects_conflicting_owner_without_partial_updates(tmp_path):
    database = str(tmp_path / "legacy-claim-conflict.sqlite3")
    directory = TenantDirectory(database)
    tenant_a = directory.create_tenant("claim-a", "Claim A")
    tenant_b = directory.create_tenant("claim-b", "Claim B")
    store = LabRunStore(database)
    run = run_lab(_request())
    store.save(run, tenant_id=tenant_a)

    with pytest.raises(LegacyClaimError, match="Conflicting existing tenant ownership"):
        claim_legacy_runs(
            database,
            [{"run_id": str(run.run_id), "tenant_id": tenant_b}],
        )

    assert store.get(run.run_id, tenant_id=tenant_a).run_id == run.run_id
    assert directory.list_audit_events(tenant_b) == []


def test_legacy_claim_apply_requires_existing_operator_principal(tmp_path):
    database = str(tmp_path / "legacy-claim-operator.sqlite3")
    directory = TenantDirectory(database)
    tenant_id = directory.create_tenant("claim-operator", "Claim Operator")
    store = LabRunStore(database)
    run = run_lab(_request())
    store.save(run)

    with pytest.raises(LegacyClaimError, match="operator principal ID"):
        claim_legacy_runs(
            database,
            [{"run_id": str(run.run_id), "tenant_id": tenant_id}],
            apply=True,
            operator_principal_id=None,
        )
    with pytest.raises(LabRunNotFound):
        store.get(run.run_id, tenant_id=tenant_id)
