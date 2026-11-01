"""Tenant directory, role matrix, and audit-event regression tests."""

from uuid import uuid4

import pytest

from artificial_scientist.authorization import (
    AuthorizationDenied,
    TenantDirectory,
    role_allows,
    stable_principal_id,
    stable_tenant_id,
)
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabExecutionNotFound, LabRunNotFound, LabRunStore


def test_principal_and_tenant_ids_are_stable_and_opaque():
    assert stable_principal_id("https://issuer.example/", "subject-1") == stable_principal_id(
        "https://issuer.example/", "subject-1"
    )
    assert stable_principal_id("https://issuer.example/", "subject-1") != stable_principal_id(
        "https://issuer.example/", "subject-2"
    )
    assert stable_tenant_id("customer-key-1") == stable_tenant_id("customer-key-1")
    assert stable_tenant_id("customer-key-1") != stable_tenant_id("customer-key-2")


def test_membership_is_explicit_and_role_permissions_deny_by_default(tmp_path):
    directory = TenantDirectory(str(tmp_path / "tenancy.sqlite3"))
    principal = directory.register_principal("https://issuer.example/", "subject-a")
    tenant_a = directory.create_tenant("tenant-a", "Tenant A")
    tenant_b = directory.create_tenant("tenant-b", "Tenant B")

    with pytest.raises(AuthorizationDenied):
        directory.authorize(principal, tenant_a, "run:read")

    directory.grant_membership(principal, tenant_a, "researcher")
    membership = directory.authorize(principal, tenant_a, "run:create")
    assert membership.role == "researcher"
    assert membership.tenant_id == tenant_a

    with pytest.raises(AuthorizationDenied):
        directory.authorize(principal, tenant_b, "run:read")
    with pytest.raises(AuthorizationDenied):
        directory.authorize(principal, tenant_a, "tenant:superuser")

    assert role_allows("viewer", "run:read")
    assert not role_allows("viewer", "run:create")
    assert not role_allows("unrecognized-role", "run:read")
    assert not role_allows("tenant_admin", "retention:purge")


def test_revoked_membership_denies_access_and_audits_both_outcomes(tmp_path):
    directory = TenantDirectory(str(tmp_path / "audit.sqlite3"))
    principal = directory.register_principal("https://issuer.example/", "subject-b")
    tenant = directory.create_tenant("tenant-a", "Tenant A")
    directory.grant_membership(principal, tenant, "viewer")
    directory.authorize(principal, tenant, "run:read")
    directory.revoke_membership(principal, tenant)

    with pytest.raises(AuthorizationDenied):
        directory.authorize(principal, tenant, "run:read")

    events = directory.list_audit_events(tenant)
    run_events = [event for event in events if event["action"] == "run:read"]
    membership_events = [
        event for event in events if event["action"] in {"membership:grant", "membership:revoke"}
    ]
    assert [event["outcome"] for event in run_events] == ["denied", "allowed"]
    assert {event["action"] for event in membership_events} == {
        "membership:grant",
        "membership:revoke",
    }
    assert all(event["principal_id"] == principal for event in events)
    assert all("metadata_json" in event for event in events)


def test_audit_rejects_oversized_metadata_and_invalid_outcome(tmp_path):
    directory = TenantDirectory(str(tmp_path / "audit-validation.sqlite3"))
    with pytest.raises(ValueError, match="outcome"):
        directory.audit(
            principal_id=None,
            tenant_id=None,
            action="run:read",
            target_type="run",
            target_id="run-1",
            outcome="success",
        )
    with pytest.raises(ValueError, match="1000 characters"):
        directory.audit(
            principal_id=None,
            tenant_id=None,
            action="run:read",
            target_type="run",
            target_id="run-1",
            outcome="failed",
            metadata={"bounded": "x" * 5000},
        )


def test_unknown_membership_role_is_rejected(tmp_path):
    directory = TenantDirectory(str(tmp_path / "roles.sqlite3"))
    principal = directory.register_principal("https://issuer.example/", "subject-c")
    tenant = directory.create_tenant("tenant-a", "Tenant A")
    with pytest.raises(ValueError, match="Unknown tenant role"):
        directory.grant_membership(principal, tenant, "owner")



@pytest.mark.parametrize(
    "metadata",
    [
        {"access_token": "should-not-be-recorded"},
        {"nested": {"request_body": "private data"}},
        {"cookie_value": "session"},
        {"too_deep": {"a": {"b": {"c": {"d": {"e": {"f": "value"}}}}}}},
        {"long_text": "x" * 1001},
        {"items": list(range(101))},
    ],
)
def test_audit_rejects_sensitive_or_unbounded_metadata(tmp_path, metadata):
    directory = TenantDirectory(str(tmp_path / "audit-safe.sqlite3"))
    with pytest.raises(ValueError):
        directory.audit(
            principal_id=None,
            tenant_id=None,
            action="run:read",
            target_type="run",
            target_id="run-1",
            outcome="failed",
            metadata=metadata,
        )


def test_audit_accepts_bounded_operational_metadata(tmp_path):
    directory = TenantDirectory(str(tmp_path / "audit-operational.sqlite3"))
    event_id = directory.audit(
        principal_id="principal-1",
        tenant_id="tenant-1",
        action="run:read",
        target_type="run",
        target_id="run-1",
        outcome="allowed",
        metadata={"http_status": 200, "route": "/api/v1/lab/runs", "attempt": 2},
    )
    assert event_id
    events = directory.list_audit_events("tenant-1")
    assert events[0]["metadata"] == {
        "http_status": 200,
        "route": "/api/v1/lab/runs",
        "attempt": 2,
    }


@pytest.mark.parametrize(
    ("role", "allowed_actions"),
    [
        (
            "tenant_admin",
            {
                "run:create", "run:list", "run:read", "run:verify", "run:export",
                "artifact:read", "artifact:upload", "membership:manage",
                "record:create", "record:read", "record:list", "record:search",
                "record:audit:read", "discovery:decompose", "discovery:generate",
                "discovery:prior-work-screen",
                "discovery:assess", "autonomy:workflow:create",
                "autonomy:workflow:read", "autonomy:workflow:write", "autonomy:workflow:approve",
                "memory:list", "memory:read", "memory:write",
                "memory:contradict", "memory:rollback",
                "manuscript:list", "manuscript:read", "manuscript:create",
            },
        ),
        (
            "researcher",
            {
                "run:create", "run:list", "run:read", "run:verify", "run:export",
                "artifact:read", "artifact:upload",
                "record:create", "record:read", "record:list", "record:search",
                "discovery:decompose", "discovery:generate", "discovery:prior-work-screen",
                "discovery:assess",
                "autonomy:workflow:create", "autonomy:workflow:read",
                "autonomy:workflow:write", "autonomy:workflow:approve",
                "memory:list", "memory:read", "memory:write",
                "memory:contradict", "memory:rollback",
                "manuscript:list", "manuscript:read", "manuscript:create",
            },
        ),
        (
            "viewer",
            {
                "run:list", "run:read", "run:export", "artifact:read",
                "record:read", "record:list", "record:search",
                "discovery:decompose", "discovery:prior-work-screen", "autonomy:workflow:read",
                "memory:list", "memory:read", "manuscript:list", "manuscript:read",
            },
        ),
        (
            "auditor",
            {
                "run:list", "run:read", "run:export", "artifact:read",
                "record:read", "record:list", "record:audit:read",
                "memory:list", "memory:read", "manuscript:list", "manuscript:read",
            },
        ),
    ],
)
def test_role_action_matrix_is_explicit(role, allowed_actions):
    from artificial_scientist.authorization import _ALLOWED_ACTIONS

    assert all(
        role_allows(role, action) == (action in allowed_actions)
        for action in _ALLOWED_ACTIONS
    )
    assert not role_allows(role, "unknown:action")


def test_hypothesis_generation_is_not_granted_to_viewers_or_auditors():
    assert role_allows("tenant_admin", "discovery:generate")
    assert role_allows("researcher", "discovery:generate")
    assert not role_allows("viewer", "discovery:generate")
    assert not role_allows("auditor", "discovery:generate")

def test_tenant_scoped_run_store_hides_foreign_and_legacy_records(tmp_path):
    store = LabRunStore(str(tmp_path / "tenant-scoped-runs.sqlite3"))
    request = LabRunRequest(
        title="Tenant ownership boundary",
        steps=[
            {
                "step_id": "stats",
                "operation": "statistics",
                "inputs": {"values": [1, 2, 3]},
            }
        ],
    )
    tenant_a = "tenant-a"
    tenant_b = "tenant-b"
    owned_run = run_lab(request)
    store.save(owned_run, tenant_id=tenant_a)

    assert store.get(owned_run.run_id, tenant_id=tenant_a).run_id == owned_run.run_id
    with pytest.raises(LabRunNotFound):
        store.get(owned_run.run_id, tenant_id=tenant_b)
    assert store.list_runs(tenant_id=tenant_b) == ([], 0)
    assert store.list_runs(tenant_id=tenant_a)[1] == 1

    legacy_run = run_lab(request)
    store.save(legacy_run)
    with pytest.raises(LabRunNotFound):
        store.get(legacy_run.run_id, tenant_id=tenant_a)
    assert store.list_runs(tenant_id=tenant_a)[1] == 1


def test_tenant_scoped_execution_status_hides_foreign_attempts(tmp_path):
    store = LabRunStore(str(tmp_path / "tenant-scoped-attempts.sqlite3"))
    run_id = uuid4()
    request = LabRunRequest(
        title="Tenant execution status boundary",
        steps=[
            {
                "step_id": "stats",
                "operation": "statistics",
                "inputs": {"values": [1, 2, 3]},
            }
        ],
    )
    store.begin_execution(run_id, request, tenant_id="tenant-a")
    assert store.get_execution_status(run_id, tenant_id="tenant-a")["run_id"] == str(run_id)
    with pytest.raises(LabExecutionNotFound):
        store.get_execution_status(run_id, tenant_id="tenant-b")


def test_autonomy_workflow_actions_follow_least_privilege():
    from artificial_scientist.authorization import role_allows

    assert role_allows("tenant_admin", "autonomy:workflow:approve")
    assert role_allows("researcher", "autonomy:workflow:approve")
    assert role_allows("viewer", "autonomy:workflow:read")
    assert not role_allows("viewer", "autonomy:workflow:approve")
    assert not role_allows("auditor", "autonomy:workflow:write")


def test_memory_actions_follow_least_privilege():
    from artificial_scientist.authorization import role_allows

    assert role_allows("tenant_admin", "memory:write")
    assert role_allows("researcher", "memory:write")
    assert role_allows("researcher", "memory:contradict")
    assert role_allows("researcher", "memory:rollback")
    assert role_allows("viewer", "memory:list")
    assert role_allows("viewer", "memory:read")
    assert role_allows("auditor", "memory:read")
    assert not role_allows("viewer", "memory:write")
    assert not role_allows("auditor", "memory:write")
    assert not role_allows("unknown", "memory:read")


def test_optional_ai_inference_permission_is_limited_to_research_roles():
    from artificial_scientist.authorization import role_allows

    assert role_allows("tenant_admin", "ai:inference")
    assert role_allows("researcher", "ai:inference")
    assert not role_allows("viewer", "ai:inference")
    assert not role_allows("auditor", "ai:inference")
    assert not role_allows("unknown", "ai:inference")
