"""PostgreSQL implementation of the tenant directory contract."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from artificial_scientist.database import get_database_engine
from artificial_scientist.authorization import (
    AuthorizationDenied,
    TenantMembership,
    TenantNotFound,
    _ALLOWED_ROLES,
    _TENANT_NAME_MAX,
    role_allows,
    stable_principal_id,
    stable_tenant_id,
)


class PostgresTenantDirectory:
    """Tenant and security-audit persistence backed by the migrated PostgreSQL schema."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine = get_database_engine(database_url)

    def register_principal(self, issuer: str, subject: str) -> str:
        if (
            not issuer.strip() or len(issuer) > 512
            or not subject.strip() or len(subject) > 255
        ):
            raise ValueError("Issuer and subject must be non-empty and bounded.")
        principal_id = stable_principal_id(issuer, subject)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO asds_principals
                    (principal_id, issuer, subject, created_at)
                    VALUES (:principal_id, :issuer, :subject, :created_at)
                    ON CONFLICT (issuer, subject) DO NOTHING"""
                ),
                {
                    "principal_id": principal_id,
                    "issuer": issuer,
                    "subject": subject,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            row = connection.execute(
                text("SELECT principal_id FROM asds_principals WHERE issuer=:issuer AND subject=:subject"),
                {"issuer": issuer, "subject": subject},
            ).mappings().one()
        return str(row["principal_id"])

    def create_tenant(self, tenant_key: str, name: str) -> str:
        if not name.strip() or len(name) > _TENANT_NAME_MAX:
            raise ValueError("Tenant name must contain 1 to 120 characters.")
        tenant_id = stable_tenant_id(tenant_key)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO asds_tenants (tenant_id, name, created_at)
                    VALUES (:tenant_id, :name, :created_at)
                    ON CONFLICT (tenant_id) DO NOTHING"""
                ),
                {
                    "tenant_id": tenant_id,
                    "name": name.strip(),
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            row = connection.execute(
                text("SELECT name FROM asds_tenants WHERE tenant_id=:tenant_id"),
                {"tenant_id": tenant_id},
            ).mappings().one()
            if row["name"] != name.strip():
                raise ValueError("Tenant key already exists with a different name.")
        return tenant_id

    def grant_membership(self, principal_id: str, tenant_id: str, role: str) -> None:
        if role not in _ALLOWED_ROLES:
            raise ValueError("Unknown tenant role.")
        now = datetime.now(UTC).isoformat()
        with self.engine.begin() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM asds_principals WHERE principal_id=:id"),
                {"id": principal_id},
            ).first()
            tenant = connection.execute(
                text("SELECT 1 FROM asds_tenants WHERE tenant_id=:id"),
                {"id": tenant_id},
            ).first()
            if exists is None or tenant is None:
                raise TenantNotFound("Principal or tenant does not exist.")
            connection.execute(
                text(
                    """INSERT INTO asds_memberships
                    (principal_id, tenant_id, role, created_at, active)
                    VALUES (:principal_id, :tenant_id, :role, :created_at, TRUE)
                    ON CONFLICT (principal_id, tenant_id) DO UPDATE
                    SET role=EXCLUDED.role, active=TRUE"""
                ),
                {
                    "principal_id": principal_id,
                    "tenant_id": tenant_id,
                    "role": role,
                    "created_at": now,
                },
            )

    def revoke_membership(self, principal_id: str, tenant_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """UPDATE asds_memberships SET active=FALSE
                    WHERE principal_id=:principal_id AND tenant_id=:tenant_id"""
                ),
                {"principal_id": principal_id, "tenant_id": tenant_id},
            )

    def authorize(self, principal_id: str, tenant_id: str, action: str) -> TenantMembership:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """SELECT role FROM asds_memberships
                    WHERE principal_id=:principal_id AND tenant_id=:tenant_id AND active=TRUE"""
                ),
                {"principal_id": principal_id, "tenant_id": tenant_id},
            ).mappings().first()
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
        import math
        import re

        if outcome not in {"allowed", "denied", "failed"}:
            raise ValueError("Unknown audit outcome.")
        if not re.fullmatch(r"[a-z][a-z0-9:_-]{0,79}", action):
            raise ValueError("Audit action must be a bounded identifier.")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", target_type):
            raise ValueError("Audit target type must be a bounded identifier.")
        safe_metadata = metadata or {}
        if not isinstance(safe_metadata, dict):
            raise ValueError("Audit metadata must be a JSON object.")
        forbidden = ("password", "secret", "token", "authorization", "credential",
                     "cookie", "payload", "request_body", "content")

        def validate(value: Any, depth: int = 0) -> None:
            if depth > 5:
                raise ValueError("Audit metadata nesting exceeds five levels.")
            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, str) or len(key) > 80:
                        raise ValueError("Audit metadata keys must be bounded strings.")
                    normalized = key.lower().replace("-", "_")
                    if any(fragment in normalized for fragment in forbidden):
                        raise ValueError("Audit metadata must not contain credentials or payloads.")
                    validate(item, depth + 1)
            elif isinstance(value, list):
                if len(value) > 100:
                    raise ValueError("Audit metadata lists are limited to 100 items.")
                for item in value:
                    validate(item, depth + 1)
            elif value is None or isinstance(value, (str, int, float, bool)):
                if isinstance(value, str) and len(value) > 1000:
                    raise ValueError("Audit metadata strings are limited to 1000 characters.")
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("Audit metadata numbers must be finite.")
            else:
                raise ValueError("Audit metadata must contain only JSON-compatible values.")

        validate(safe_metadata)
        encoded = json.dumps(
            safe_metadata, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        if len(encoded.encode("utf-8")) > 4096:
            raise ValueError("Audit metadata exceeds 4 KiB.")
        event_id = str(uuid4())
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO asds_security_audit
                    (event_id, occurred_at, principal_id, tenant_id, action, target_type,
                     target_id, outcome, correlation_id, metadata_json)
                    VALUES (:event_id, :occurred_at, :principal_id, :tenant_id, :action,
                     :target_type, :target_id, :outcome, :correlation_id, :metadata_json)"""
                ),
                {
                    "event_id": event_id,
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "principal_id": principal_id,
                    "tenant_id": tenant_id,
                    "action": action,
                    "target_type": target_type,
                    "target_id": target_id,
                    "outcome": outcome,
                    "correlation_id": correlation_id,
                    "metadata_json": encoded,
                },
            )
        return event_id

    def list_audit_events(
        self, tenant_id: str | None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise ValueError("Audit page size must be between 1 and 500.")
        predicate = "tenant_id IS NULL" if tenant_id is None else "tenant_id=:tenant_id"
        params: dict[str, Any] = {"limit": limit}
        if tenant_id is not None:
            params["tenant_id"] = tenant_id
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""SELECT event_id, occurred_at, principal_id, tenant_id, action,
                    target_type, target_id, outcome, correlation_id, metadata_json
                    FROM asds_security_audit WHERE {predicate}
                    ORDER BY occurred_at DESC, event_id DESC LIMIT :limit"""
                ),
                params,
            ).mappings().all()
        return [
            {**dict(row), "metadata": json.loads(row["metadata_json"])}
            for row in rows
        ]
