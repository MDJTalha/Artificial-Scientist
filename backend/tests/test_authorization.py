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
    assert [event["outcome"] for event in events] == ["denied", "allowed"]
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
