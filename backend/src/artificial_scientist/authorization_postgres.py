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
        # Reuse the exact validation policy of the SQLite implementation.
        from artificial_scientist.authorization import validate_audit_metadata

        encoded = validate_audit_metadata(
            action=action, target_type=target_type, outcome=outcome, metadata=metadata
        )
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
