"""SQLite persistence for tenant-scoped bounded autonomy state and scientific memory."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class AutonomyStore:
    """Transactional journal with fail-closed tenant ownership."""

    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _init(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS autonomy_workflows (
                  workflow_id TEXT PRIMARY KEY,
                  state TEXT NOT NULL,
                  consequential INTEGER NOT NULL,
                  approval_token_hash TEXT,
                  tenant_id TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS autonomy_transitions (
                  event_id TEXT PRIMARY KEY,
                  workflow_id TEXT NOT NULL,
                  from_state TEXT NOT NULL,
                  to_state TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  reason TEXT NOT NULL,
                  tenant_id TEXT,
                  occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS autonomy_checkpoints (
                  checkpoint_id TEXT PRIMARY KEY,
                  workflow_id TEXT NOT NULL,
                  digest TEXT NOT NULL,
                  tenant_id TEXT,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS autonomy_memory (
                  memory_id TEXT PRIMARY KEY,
                  key_name TEXT NOT NULL,
                  version INTEGER NOT NULL,
                  status TEXT NOT NULL,
                  value_json TEXT NOT NULL,
                  evidence_json TEXT NOT NULL,
                  digest TEXT NOT NULL,
                  supersedes_version INTEGER,
                  tenant_id TEXT,
                  created_at TEXT NOT NULL,
                  UNIQUE(key_name, version, tenant_id)
                );
                CREATE INDEX IF NOT EXISTS idx_autonomy_memory_key
                  ON autonomy_memory(tenant_id, key_name, version);
                """
            )
            self._ensure_column(connection, "autonomy_workflows", "tenant_id")
            self._ensure_column(connection, "autonomy_transitions", "tenant_id")
            self._ensure_column(connection, "autonomy_checkpoints", "tenant_id")
            self._ensure_column(connection, "autonomy_memory", "tenant_id")
            connection.commit()

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection, table: str, column: str
    ) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")

    @staticmethod
    def _require_tenant(tenant_id: str | None) -> str:
        if not tenant_id or len(tenant_id) > 200:
            raise ValueError("tenant_id is required")
        return tenant_id

    def save_workflow(
        self,
        workflow_id: str,
        state: str,
        consequential: bool,
        approval_token_hash: str | None,
        *,
        tenant_id: str,
    ) -> None:
        tenant = self._require_tenant(tenant_id)
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO autonomy_workflows "
                "(workflow_id,state,consequential,approval_token_hash,tenant_id,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    workflow_id,
                    state,
                    int(consequential),
                    approval_token_hash,
                    tenant,
                    now,
                    now,
                ),
            )
            connection.commit()

    def transition(
        self,
        workflow_id: str,
        from_state: str,
        to_state: str,
        actor: str,
        reason: str,
        *,
        tenant_id: str,
    ) -> None:
        tenant = self._require_tenant(tenant_id)
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE autonomy_workflows SET state=?, updated_at=? "
                "WHERE workflow_id=? AND state=? AND tenant_id=?",
                (to_state, now, workflow_id, from_state, tenant),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ValueError("workflow state changed concurrently or is not owned")
            connection.execute(
                "INSERT INTO autonomy_transitions "
                "(event_id,workflow_id,from_state,to_state,actor,reason,tenant_id,occurred_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    workflow_id,
                    from_state,
                    to_state,
                    actor,
                    reason,
                    tenant,
                    now,
                ),
            )
            connection.commit()

    def approve(
        self,
        workflow_id: str,
        from_state: str,
        approval_token_hash: str,
        actor: str,
        *,
        tenant_id: str,
    ) -> None:
        tenant = self._require_tenant(tenant_id)
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE autonomy_workflows SET state=?, approval_token_hash=?, updated_at=? "
                "WHERE workflow_id=? AND state=? AND tenant_id=?",
                (
                    "approved",
                    approval_token_hash,
                    now,
                    workflow_id,
                    from_state,
                    tenant,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ValueError("workflow approval changed concurrently or is not owned")
            connection.execute(
                "INSERT INTO autonomy_transitions "
                "(event_id,workflow_id,from_state,to_state,actor,reason,tenant_id,occurred_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    workflow_id,
                    from_state,
                    "approved",
                    actor,
                    "explicit approval",
                    tenant,
                    now,
                ),
            )
            connection.commit()

    def checkpoint(self, workflow_id: str, digest: str, *, tenant_id: str) -> None:
        tenant = self._require_tenant(tenant_id)
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO autonomy_checkpoints "
                "(checkpoint_id,workflow_id,digest,tenant_id,created_at) VALUES(?,?,?,?,?)",
                (
                    str(uuid4()),
                    workflow_id,
                    digest,
                    tenant,
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.commit()

    def workflow(self, workflow_id: str, *, tenant_id: str) -> dict:
        tenant = self._require_tenant(tenant_id)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM autonomy_workflows "
                "WHERE workflow_id=? AND tenant_id=?",
                (workflow_id, tenant),
            ).fetchone()
        if row is None:
            raise KeyError(workflow_id)
        return dict(row)

    def transitions(self, workflow_id: str, *, tenant_id: str) -> list[dict]:
        tenant = self._require_tenant(tenant_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM autonomy_transitions "
                "WHERE workflow_id=? AND tenant_id=? "
                "ORDER BY occurred_at, event_id",
                (workflow_id, tenant),
            ).fetchall()
        return [dict(row) for row in rows]

    def checkpoints(self, workflow_id: str, *, tenant_id: str) -> list[dict]:
        tenant = self._require_tenant(tenant_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM autonomy_checkpoints "
                "WHERE workflow_id=? AND tenant_id=? ORDER BY created_at, checkpoint_id",
                (workflow_id, tenant),
            ).fetchall()
        return [dict(row) for row in rows]

    def memory_put(
        self,
        key: str,
        value: dict,
        status: str,
        evidence: tuple[str, ...],
        digest: str,
        supersedes_version: int | None,
        *,
        tenant_id: str,
    ) -> int:
        tenant = self._require_tenant(tenant_id)
        storage_key = f"{tenant}:{key}"
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM autonomy_memory "
                "WHERE key_name=? AND tenant_id=?",
                (storage_key, tenant),
            ).fetchone()
            version = int(row[0]) + 1
            connection.execute(
                "INSERT INTO autonomy_memory "
                "(memory_id,key_name,version,status,value_json,evidence_json,digest,"
                "supersedes_version,tenant_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    storage_key,
                    version,
                    status,
                    json.dumps(value, sort_keys=True),
                    json.dumps(evidence),
                    digest,
                    supersedes_version,
                    tenant,
                    now,
                ),
            )
            connection.commit()
        return version

    def memory_keys(self, *, tenant_id: str) -> list[str]:
        tenant = self._require_tenant(tenant_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT DISTINCT key_name FROM autonomy_memory "
                "WHERE tenant_id=? ORDER BY key_name",
                (tenant,),
            ).fetchall()
        prefix = f"{tenant}:"
        return [str(row[0])[len(prefix):] for row in rows if str(row[0]).startswith(prefix)]

    def memory_history(self, key: str, *, tenant_id: str) -> list[dict]:
        tenant = self._require_tenant(tenant_id)
        storage_key = f"{tenant}:{key}"
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM autonomy_memory "
                "WHERE key_name=? AND tenant_id=? ORDER BY version",
                (storage_key, tenant),
            ).fetchall()
        return [dict(row) for row in rows]
