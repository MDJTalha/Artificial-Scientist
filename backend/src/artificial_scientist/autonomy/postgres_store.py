"""PostgreSQL persistence for tenant-scoped autonomy workflows and scientific memory."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

from artificial_scientist.database import get_database_engine


class PostgresAutonomyStore:
    """Transactional PostgreSQL implementation of the AutonomyStore contract."""

    def __init__(self, database_url: str) -> None:
        self.engine = get_database_engine(database_url)

    @staticmethod
    def _require_tenant(tenant_id: str | None) -> str:
        if not tenant_id or len(tenant_id) > 200:
            raise ValueError("tenant_id is required")
        return tenant_id

    def save_workflow(
        self, workflow_id: str, state: str, consequential: bool,
        approval_token_hash: str | None, *, tenant_id: str,
    ) -> None:
        tenant = self._require_tenant(tenant_id)
        now = datetime.now(UTC).isoformat()
        with self.engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO autonomy_workflows
                (workflow_id,state,consequential,approval_token_hash,tenant_id,created_at,updated_at)
                VALUES (:workflow_id,:state,:consequential,:approval_token_hash,\n                        :tenant_id,:now,:now)
            """), {
                "workflow_id": workflow_id, "state": state,
                "consequential": consequential, "approval_token_hash": approval_token_hash,
                "tenant_id": tenant, "now": now,
            })

    def transition(
        self, workflow_id: str, from_state: str, to_state: str,
        actor: str, reason: str, *, tenant_id: str,
    ) -> None:
        tenant = self._require_tenant(tenant_id)
        now = datetime.now(UTC).isoformat()
        with self.engine.begin() as connection:
            changed = connection.execute(text("""
                UPDATE autonomy_workflows SET state=:to_state, updated_at=:now
                WHERE workflow_id=:workflow_id AND state=:from_state AND tenant_id=:tenant_id
            """), {
                "to_state": to_state, "now": now, "workflow_id": workflow_id,
                "from_state": from_state, "tenant_id": tenant,
            })
            if changed.rowcount != 1:
                raise ValueError("workflow state changed concurrently or is not owned")
            connection.execute(text("""
                INSERT INTO autonomy_transitions
                (event_id,workflow_id,from_state,to_state,actor,reason,tenant_id,occurred_at)
                VALUES (:event_id,:workflow_id,:from_state,:to_state,:actor,:reason,:tenant_id,:now)
            """), {
                "event_id": str(uuid4()), "workflow_id": workflow_id,
                "from_state": from_state, "to_state": to_state, "actor": actor,
                "reason": reason, "tenant_id": tenant, "now": now,
            })

    def approve(
        self, workflow_id: str, from_state: str, approval_token_hash: str,
        actor: str, *, tenant_id: str,
    ) -> None:
        tenant = self._require_tenant(tenant_id)
        now = datetime.now(UTC).isoformat()
        with self.engine.begin() as connection:
            changed = connection.execute(text("""
                UPDATE autonomy_workflows
                SET state='approved', approval_token_hash=:approval_token_hash, updated_at=:now
                WHERE workflow_id=:workflow_id AND state=:from_state AND tenant_id=:tenant_id
            """), {
                "approval_token_hash": approval_token_hash, "now": now,
                "workflow_id": workflow_id, "from_state": from_state, "tenant_id": tenant,
            })
            if changed.rowcount != 1:
                raise ValueError("workflow approval changed concurrently or is not owned")
            connection.execute(text("""
                INSERT INTO autonomy_transitions
                (event_id,workflow_id,from_state,to_state,actor,reason,tenant_id,occurred_at)
                VALUES (:event_id,:workflow_id,:from_state,'approved',:actor,
                        'explicit approval',:tenant_id,:now)
            """), {
                "event_id": str(uuid4()), "workflow_id": workflow_id,
                "from_state": from_state, "actor": actor, "tenant_id": tenant, "now": now,
            })

    def checkpoint(self, workflow_id: str, digest: str, *, tenant_id: str) -> None:
        tenant = self._require_tenant(tenant_id)
        with self.engine.begin() as connection:
            owned = connection.execute(text("""
                SELECT 1 FROM autonomy_workflows\n                WHERE workflow_id=:workflow_id AND tenant_id=:tenant_id
            """), {"workflow_id": workflow_id, "tenant_id": tenant}).first()
            if owned is None:
                raise KeyError(workflow_id)
            connection.execute(text("""
                INSERT INTO autonomy_checkpoints
                (checkpoint_id,workflow_id,digest,tenant_id,created_at)
                VALUES (:id,:workflow_id,:digest,:tenant_id,:now)
            """), {
                "id": str(uuid4()), "workflow_id": workflow_id, "digest": digest,
                "tenant_id": tenant, "now": datetime.now(UTC).isoformat(),
            })

    def workflow(self, workflow_id: str, *, tenant_id: str) -> dict:
        tenant = self._require_tenant(tenant_id)
        with self.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT * FROM autonomy_workflows\n                WHERE workflow_id=:workflow_id AND tenant_id=:tenant_id
            """), {"workflow_id": workflow_id, "tenant_id": tenant}).mappings().first()
        if row is None:
            raise KeyError(workflow_id)
        return dict(row)

    def transitions(self, workflow_id: str, *, tenant_id: str) -> list[dict]:
        tenant = self._require_tenant(tenant_id)
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT * FROM autonomy_transitions
                WHERE workflow_id=:workflow_id AND tenant_id=:tenant_id
                ORDER BY occurred_at,event_id
            """), {"workflow_id": workflow_id, "tenant_id": tenant}).mappings().all()
        return [dict(row) for row in rows]

    def checkpoints(self, workflow_id: str, *, tenant_id: str) -> list[dict]:
        tenant = self._require_tenant(tenant_id)
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT * FROM autonomy_checkpoints
                WHERE workflow_id=:workflow_id AND tenant_id=:tenant_id
                ORDER BY created_at,checkpoint_id
            """), {"workflow_id": workflow_id, "tenant_id": tenant}).mappings().all()
        return [dict(row) for row in rows]

    def memory_put(
        self, key: str, value: dict, status: str, evidence: tuple[str, ...],
        digest: str, supersedes_version: int | None, *, tenant_id: str,
    ) -> int:
        tenant = self._require_tenant(tenant_id)
        now = datetime.now(UTC).isoformat()
        with self.engine.begin() as connection:
            # Serialize version allocation for a tenant/key pair, including the
            # first insert where no row exists yet.
            connection.execute(text("""
                SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))
            """), {"scope": tenant + ":" + key})
            current = connection.execute(text("""
                SELECT COALESCE(MAX(version),0) FROM autonomy_memory
                WHERE key_name=:key AND tenant_id=:tenant_id
            """), {"key": key, "tenant_id": tenant}).scalar_one()
            version = int(current) + 1
            connection.execute(text("""
                INSERT INTO autonomy_memory
                (memory_id,key_name,version,status,value_json,evidence_json,digest,
                 supersedes_version,tenant_id,created_at)
                VALUES (:id,:key,:version,:status,:value,:evidence,:digest,
                        :supersedes,:tenant_id,:now)
            """), {
                "id": str(uuid4()), "key": key, "version": version, "status": status,
                "value": json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False),
                "evidence": json.dumps(evidence, separators=(",", ":"), allow_nan=False),
                "digest": digest, "supersedes": supersedes_version,
                "tenant_id": tenant, "now": now,
            })
        return version

    def memory_keys(self, *, tenant_id: str) -> list[str]:
        tenant = self._require_tenant(tenant_id)
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT DISTINCT key_name FROM autonomy_memory
                WHERE tenant_id=:tenant_id ORDER BY key_name
            """), {"tenant_id": tenant}).scalars().all()
        return [str(value) for value in rows]

    def memory_history(self, key: str, *, tenant_id: str) -> list[dict]:
        tenant = self._require_tenant(tenant_id)
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT * FROM autonomy_memory
                WHERE key_name=:key AND tenant_id=:tenant_id ORDER BY version
            """), {"key": key, "tenant_id": tenant}).mappings().all()
        return [dict(row) for row in rows]
