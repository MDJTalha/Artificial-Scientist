"""Persistence primitives for principals, tenants, memberships, and security audit events.

This module intentionally does not grant access based on client-supplied tenant IDs.
Callers must authenticate first and authorize membership/role before any protected action.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

_SUBJECT_MAX = 255
_TENANT_NAME_MAX = 120
_ALLOWED_ROLES = frozenset({"tenant_admin", "researcher", "viewer", "auditor"})
_LAB_ACTIONS = frozenset({
    "run:create", "run:list", "run:read", "run:verify", "run:export",
    "artifact:read", "artifact:upload", "membership:manage", "retention:purge",
})
_RECORD_ACTIONS = frozenset({
    "record:create", "record:read", "record:list", "record:search",
    "record:audit:read", "discovery:decompose", "discovery:prior-work-screen",
    "discovery:assess",
})
_ALLOWED_ACTIONS = _LAB_ACTIONS | _RECORD_ACTIONS


class AuthorizationDenied(PermissionError):
    """Raised when a principal has no active membership or sufficient role."""


class TenantNotFound(LookupError):
    """Raised when a tenant is unavailable to the current principal."""


@dataclass(frozen=True, slots=True)
class TenantMembership:
    principal_id: str
    tenant_id: str
    role: str


def stable_principal_id(issuer: str, subject: str) -> str:
    """Derive an immutable opaque principal ID from a trusted issuer/subject pair."""
    if not issuer.strip() or not subject.strip() or len(subject) > _SUBJECT_MAX:
        raise ValueError("Issuer and bounded subject are required.")
    return str(uuid5(NAMESPACE_URL, f"asds:principal:{issuer}:{subject}"))


def stable_tenant_id(external_key: str) -> str:
    """Derive a stable opaque tenant ID from an operator-controlled external key."""
    if not external_key.strip() or len(external_key) > 512:
        raise ValueError("A bounded tenant key is required.")
    digest = hashlib.sha256(external_key.encode("utf-8")).hexdigest()
    return str(uuid5(NAMESPACE_URL, f"asds:tenant:{digest}"))


def role_allows(role: str, action: str) -> bool:
    """Return explicit least-privilege permissions for lab and research APIs."""
    if role not in _ALLOWED_ROLES or action not in _ALLOWED_ACTIONS:
        return False
    if role == "tenant_admin":
        return action != "retention:purge"
    if action in _RECORD_ACTIONS:
        if role == "researcher":
            return action in {
                "record:create", "record:read", "record:list", "record:search",
                "discovery:decompose", "discovery:prior-work-screen", "discovery:assess",
            }
        if role == "viewer":
            return action in {
                "record:read", "record:list", "record:search",
                "discovery:decompose", "discovery:prior-work-screen",
            }
        if role == "auditor":
            return action in {"record:read", "record:list", "record:audit:read"}
        return False
    if role == "researcher":
        return action in {
            "run:create", "run:list", "run:read", "run:verify", "run:export",
            "artifact:read", "artifact:upload",
        }
    if role in {"viewer", "auditor"}:
        return action in {"run:list", "run:read", "run:export", "artifact:read"}
    return False


class TenantDirectory:
    """SQLite-backed tenant directory; membership grants are explicit and audited."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS asds_principals (
                    principal_id TEXT PRIMARY KEY,
                    issuer TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (issuer, subject)
                );
                CREATE TABLE IF NOT EXISTS asds_tenants (
                    tenant_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS asds_memberships (
                    principal_id TEXT NOT NULL REFERENCES asds_principals(principal_id)
                        ON DELETE CASCADE,
                    tenant_id TEXT NOT NULL REFERENCES asds_tenants(tenant_id)
                        ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN (
                        'tenant_admin','researcher','viewer','auditor'
                    )),
                    created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    PRIMARY KEY(principal_id, tenant_id)
                );
                CREATE INDEX IF NOT EXISTS idx_asds_memberships_tenant
                    ON asds_memberships(tenant_id, active);
                CREATE TABLE IF NOT EXISTS asds_security_audit (
                    event_id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    principal_id TEXT,
                    tenant_id TEXT,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT,
                    outcome TEXT NOT NULL CHECK(outcome IN ('allowed','denied','failed')),
                    correlation_id TEXT,
                    metadata_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asds_audit_tenant_time
                    ON asds_security_audit(tenant_id, occurred_at DESC);
                """
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def register_principal(self, issuer: str, subject: str) -> str:
        principal_id = stable_principal_id(issuer, subject)
        if (
            not issuer.strip()
            or len(issuer) > 512
            or not subject.strip()
            or len(subject) > _SUBJECT_MAX
        ):
            raise ValueError("Issuer and subject must be non-empty and bounded.")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """INSERT INTO asds_principals(principal_id,issuer,subject,created_at)
                    VALUES(?,?,?,?) ON CONFLICT(issuer,subject) DO NOTHING""",
                    (principal_id, issuer, subject, datetime.now(UTC).isoformat()),
                )
                row = connection.execute(
                    "SELECT principal_id FROM asds_principals WHERE issuer=? AND subject=?",
                    (issuer, subject),
                ).fetchone()
        return str(row["principal_id"])

    def create_tenant(self, tenant_key: str, name: str) -> str:
        if not name.strip() or len(name) > _TENANT_NAME_MAX:
            raise ValueError("Tenant name must contain 1 to 120 characters.")
        tenant_id = stable_tenant_id(tenant_key)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT OR IGNORE INTO asds_tenants(tenant_id,name,created_at) VALUES(?,?,?)",
                    (tenant_id, name.strip(), datetime.now(UTC).isoformat()),
                )
                row = connection.execute(
                    "SELECT name FROM asds_tenants WHERE tenant_id=?", (tenant_id,)
                ).fetchone()
                if row["name"] != name.strip():
                    raise ValueError("Tenant key already exists with a different name.")
        return tenant_id

    def grant_membership(self, principal_id: str, tenant_id: str, role: str) -> None:
        if role not in _ALLOWED_ROLES:
            raise ValueError("Unknown tenant role.")
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection:
            with connection:
                exists = connection.execute(
                    "SELECT 1 FROM asds_principals WHERE principal_id=?", (principal_id,)
                ).fetchone()
                tenant = connection.execute(
                    "SELECT 1 FROM asds_tenants WHERE tenant_id=?", (tenant_id,)
                ).fetchone()
                if exists is None or tenant is None:
                    raise TenantNotFound("Principal or tenant does not exist.")
                connection.execute(
                    """INSERT INTO asds_memberships(principal_id,tenant_id,role,created_at,active)
                    VALUES(?,?,?,?,1) ON CONFLICT(principal_id,tenant_id) DO UPDATE
                    SET role=excluded.role, active=1""",
                    (principal_id, tenant_id, role, now),
                )

    def revoke_membership(self, principal_id: str, tenant_id: str) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "UPDATE asds_memberships SET active=0 WHERE principal_id=? AND tenant_id=?",
                    (principal_id, tenant_id),
                )

    def authorize(self, principal_id: str, tenant_id: str, action: str) -> TenantMembership:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT role FROM asds_memberships
                WHERE principal_id=? AND tenant_id=? AND active=1""",
                (principal_id, tenant_id),
            ).fetchone()
        if row is None or not role_allows(str(row["role"]), action):
            self.audit(
                principal_id=principal_id, tenant_id=tenant_id, action=action,
                target_type="tenant", target_id=tenant_id, outcome="denied",
            )
            raise AuthorizationDenied("Tenant membership or permission is required.")
        self.audit(
            principal_id=principal_id, tenant_id=tenant_id, action=action,
            target_type="tenant", target_id=tenant_id, outcome="allowed",
        )
        return TenantMembership(principal_id, tenant_id, str(row["role"]))

    def audit(
        self, *, principal_id: str | None, tenant_id: str | None, action: str,
        target_type: str, target_id: str | None, outcome: str,
        correlation_id: str | None = None, metadata: dict[str, Any] | None = None,
    ) -> str:
        """Append a bounded audit event; credentials and raw payloads are not accepted."""
        if outcome not in {"allowed", "denied", "failed"}:
            raise ValueError("Unknown audit outcome.")
        if not re.fullmatch(r"[a-z][a-z0-9:_-]{0,79}", action):
            raise ValueError("Audit action must be a bounded identifier.")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", target_type):
            raise ValueError("Audit target type must be a bounded identifier.")
        safe_metadata = metadata or {}
        if not isinstance(safe_metadata, dict):
            raise ValueError("Audit metadata must be a JSON object.")
        forbidden_key_fragments = (
            "password", "secret", "token", "authorization", "credential",
            "cookie", "payload", "request_body", "content",
        )

        def validate_metadata(value: Any, depth: int = 0) -> None:
            if depth > 5:
                raise ValueError("Audit metadata nesting exceeds five levels.")
            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, str) or len(key) > 80:
                        raise ValueError("Audit metadata keys must be bounded strings.")
                    normalized_key = key.lower().replace("-", "_")
                    if any(fragment in normalized_key for fragment in forbidden_key_fragments):
                        raise ValueError("Audit metadata must not contain credentials or payloads.")
                    validate_metadata(item, depth + 1)
            elif isinstance(value, list):
                if len(value) > 100:
                    raise ValueError("Audit metadata lists are limited to 100 items.")
                for item in value:
                    validate_metadata(item, depth + 1)
            elif value is None or isinstance(value, (str, int, float, bool)):
                if isinstance(value, str) and len(value) > 1000:
                    raise ValueError("Audit metadata strings are limited to 1000 characters.")
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("Audit metadata numbers must be finite.")
            else:
                raise ValueError("Audit metadata must contain only JSON-compatible values.")

        validate_metadata(safe_metadata)
        encoded = json.dumps(
            safe_metadata, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        if len(encoded.encode("utf-8")) > 4096:
            raise ValueError("Audit metadata exceeds 4 KiB.")
        event_id = str(uuid4())
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """INSERT INTO asds_security_audit
                    (event_id,occurred_at,principal_id,tenant_id,action,target_type,target_id,
                     outcome,correlation_id,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (event_id, datetime.now(UTC).isoformat(), principal_id, tenant_id,
                     action, target_type, target_id, outcome, correlation_id, encoded),
                )
        return event_id

    def list_audit_events(
        self, tenant_id: str | None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise ValueError("Audit page size must be between 1 and 500.")
        tenant_filter = "tenant_id IS NULL" if tenant_id is None else "tenant_id=?"
        parameters: tuple[object, ...] = (limit,) if tenant_id is None else (tenant_id, limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""SELECT event_id,occurred_at,principal_id,tenant_id,action,target_type,
                target_id,outcome,correlation_id,metadata_json FROM asds_security_audit
                WHERE {tenant_filter} ORDER BY occurred_at DESC,event_id DESC LIMIT ?""",
                parameters,
            ).fetchall()
        return [
            {**dict(row), "metadata": json.loads(row["metadata_json"])}
            for row in rows
        ]
