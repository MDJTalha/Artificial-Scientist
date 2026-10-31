"""Least-privilege regression tests for the Phase 7 record policy."""
import pytest

from artificial_scientist.records.tenant_policy import (
    RECORD_ACTIONS,
    record_role_allows,
)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("tenant_admin", RECORD_ACTIONS),
        ("researcher", RECORD_ACTIONS - {"record:audit:read"}),
        (
            "viewer",
            {
                "record:read", "record:list", "record:search",
                "discovery:decompose", "discovery:prior-work-screen",
            },
        ),
        ("auditor", {"record:read", "record:list", "record:audit:read"}),
    ],
)
def test_role_matrix_is_explicit(role, expected):
    allowed = {
        action for action in RECORD_ACTIONS if record_role_allows(role, action)
    }
    assert allowed == set(expected)


@pytest.mark.parametrize("role", ["unknown", "", "admin", "service"])
def test_unknown_roles_deny_all_record_actions(role):
    assert all(not record_role_allows(role, action) for action in RECORD_ACTIONS)


@pytest.mark.parametrize(
    "action",
    [
        "record:delete",
        "record:tenant:override",
        "discovery:admin",
        "record:audit:write",
        "unknown:action",
    ],
)
def test_unknown_actions_deny_even_for_tenant_admin(action):
    assert not record_role_allows("tenant_admin", action)
