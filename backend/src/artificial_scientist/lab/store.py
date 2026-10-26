"""SQLite persistence for completed controlled-lab run records."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from uuid import UUID

from artificial_scientist.lab.models import LabRunResponse


class LabRunNotFound(LookupError):
    """Raised when a requested run ID is not present in the lab store."""


class LabRunStore:
    """Persist bounded run responses in the configured application SQLite database."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS lab_runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
                    configuration_sha256 TEXT NOT NULL CHECK (length(configuration_sha256) = 64),
                    result_sha256 TEXT NOT NULL CHECK (length(result_sha256) = 64),
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_lab_runs_created_at ON lab_runs(created_at DESC)"
            )
            connection.commit()

    def save(self, run: LabRunResponse) -> LabRunResponse:
        payload = json.dumps(
            run.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO lab_runs (
                    run_id, status, configuration_sha256, result_sha256, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(run.run_id),
                    run.status,
                    run.configuration_sha256,
                    run.result_sha256,
                    run.started_at,
                    payload,
                ),
            )
            connection.commit()
        return run

    @staticmethod
    def _verify_result_hash(run: LabRunResponse) -> None:
        """Verify the stored step payload against the digest recorded at execution."""
        canonical = json.dumps(
            {
                "run_id": str(run.run_id),
                "configuration_sha256": run.configuration_sha256,
                "status": run.status,
                "steps": [step.model_dump(mode="json") for step in run.steps],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if actual != run.result_sha256:
            raise RuntimeError("Stored lab run result hash does not match its payload.")

    def get(self, run_id: UUID) -> LabRunResponse:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM lab_runs WHERE run_id = ?",
                (str(run_id),),
            ).fetchone()
        if row is None:
            raise LabRunNotFound(str(run_id))
        try:
            payload: dict[str, Any] = json.loads(row["payload_json"])
            run = LabRunResponse.model_validate(payload)
            self._verify_result_hash(run)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise RuntimeError("Stored lab run failed schema validation.") from error
        return run

    def list_runs(self, limit: int = 20, offset: int = 0) -> tuple[list[LabRunResponse], int]:
        with self._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM lab_runs").fetchone()[0])
            rows = connection.execute(
                "SELECT payload_json FROM lab_runs ORDER BY created_at DESC, run_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        runs: list[LabRunResponse] = []
        for row in rows:
            try:
                run = LabRunResponse.model_validate(json.loads(row["payload_json"]))
                self._verify_result_hash(run)
                runs.append(run)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                raise RuntimeError("Stored lab run failed schema validation.") from error
        return runs, total
