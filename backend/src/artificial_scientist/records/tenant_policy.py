"""Least-privilege action policy for tenant-scoped research records.

This module deliberately contains policy only. It does not treat X-Tenant-ID as
proof of membership; API dependencies must authenticate the principal and call
TenantDirectory.authorize before passing the resulting tenant ID to storage.
"""
from __future__ import annotations

RECORD_ACTIONS = frozenset({
    "record:create",
    "record:read",
    "record:list",
    "record:search",
    "record:audit:read",
    "discovery:decompose",
    "discovery:generate",
    "discovery:prior-work-screen",
    "discovery:assess",
    "memory:list", "memory:read", "memory:write",
    "memory:contradict", "memory:rollback",
    "manuscript:list", "manuscript:read", "manuscript:create",
    "ai:inference",
})

# Explicit permissions prevent an unknown role or action from inheriting access.
_ROLE_ACTIONS = {
    "tenant_admin": frozenset({
        "record:create", "record:read", "record:list", "record:search",
        "record:audit:read", "discovery:decompose", "discovery:generate",
        "discovery:prior-work-screen",
        "discovery:assess",
        "memory:list", "memory:read", "memory:write", "memory:contradict", "memory:rollback",
        "manuscript:list", "manuscript:read", "manuscript:create",
    }),
    "researcher": frozenset({
        "record:create", "record:read", "record:list", "record:search",
        "discovery:decompose", "discovery:generate", "discovery:prior-work-screen",
        "discovery:assess",
        "memory:list", "memory:read", "memory:write", "memory:contradict", "memory:rollback",
        "manuscript:list", "manuscript:read", "manuscript:create",
        "ai:inference",
    }),
    "viewer": frozenset({
        "record:read", "record:list", "record:search",
        "discovery:decompose", "discovery:prior-work-screen",
        "memory:list", "memory:read", "manuscript:list", "manuscript:read",
    }),
    "auditor": frozenset({
        "record:read", "record:list", "record:audit:read",
        "memory:list", "memory:read", "manuscript:list", "manuscript:read",
    }),
}


def record_role_allows(role: str, action: str) -> bool:
    """Return whether a known role may perform an explicitly listed record action."""
    return action in RECORD_ACTIONS and action in _ROLE_ACTIONS.get(role, frozenset())
