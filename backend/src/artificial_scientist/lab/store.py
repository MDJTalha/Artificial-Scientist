"""SQLite persistence for controlled-lab runs and immutable JSON artifacts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from artificial_scientist.lab.integrity import result_digest
from artificial_scientist.lab.models import (
    LabArtifactMetadata,
    LabArtifactResponse,
    LabRunResponse,
)

_MAX_ARTIFACT_BYTES = 1_048_576


class LabRunNotFound(LookupError):
    """Raised when a requested run ID is not present in the lab store."""


class LabArtifactNotFound(LookupError):
    """Raised when a requested artifact ID is not present in the lab store."""


class LabRunStore:
    """Persist run records and their content-addressed, provenance-linked artifacts."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS lab_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES lab_runs(run_id) ON DELETE CASCADE,
                    artifact_type TEXT NOT NULL CHECK (artifact_type = 'run-result-json'),
                    content_type TEXT NOT NULL CHECK (content_type = 'application/json'),
                    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
                    size_bytes INTEGER NOT NULL CHECK (size_bytes BETWEEN 0 AND 1048576),
                    created_at TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    content_json BLOB NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_lab_artifacts_run_id ON lab_artifacts(run_id)"
            )
            connection.commit()

    @staticmethod
    def _canonical_json(value: object) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @staticmethod
    def _verify_result_hash(
        run: LabRunResponse, original_payload: dict[str, Any] | None = None
    ) -> None:
        """Verify persisted fields while remaining compatible with older response schemas."""
        payload = original_payload if original_payload is not None else run.model_dump(mode="json")
        if result_digest(payload) != run.result_sha256:
            raise RuntimeError("Stored lab run result hash does not match its payload.")

    @staticmethod
    def _artifact_metadata(row: sqlite3.Row) -> LabArtifactMetadata:
        return LabArtifactMetadata(
            artifact_id=row["artifact_id"],
            run_id=row["run_id"],
            artifact_type=row["artifact_type"],
            content_type=row["content_type"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            created_at=row["created_at"],
            provenance=json.loads(row["provenance_json"]),
        )

    def save(self, run: LabRunResponse) -> LabRunResponse:
        """Atomically save a run and its immutable JSON result artifact."""
        self._verify_result_hash(run)
        run_payload = self._canonical_json(run.model_dump(mode="json"))
        artifact_bytes = run_payload.encode("utf-8")
        if len(artifact_bytes) > _MAX_ARTIFACT_BYTES:
            raise ValueError("Run result artifact exceeds the 1 MiB storage limit.")

        artifact_id = uuid5(NAMESPACE_URL, f"artificial-scientist:run:{run.run_id}:result")
        created_at = datetime.now(UTC).isoformat()
        provenance = {
            "run_id": str(run.run_id),
            "title": run.title,
            "status": run.status,
            "configuration_sha256": run.configuration_sha256,
            "result_sha256": run.result_sha256,
            "plan_record_id": str(run.plan_record_id) if run.plan_record_id else None,
            "step_ids": [step.step_id for step in run.steps],
            "artifact_role": "canonical-run-result",
        }
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO lab_runs (
                        run_id, status, configuration_sha256, result_sha256,
                        created_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(run.run_id),
                        run.status,
                        run.configuration_sha256,
                        run.result_sha256,
                        run.started_at,
                        run_payload,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO lab_artifacts (
                        artifact_id, run_id, artifact_type, content_type, sha256,
                        size_bytes, created_at, provenance_json, content_json
                    ) VALUES (?, ?, 'run-result-json', 'application/json', ?, ?, ?, ?, ?)
                    """,
                    (
                        str(artifact_id),
                        str(run.run_id),
                        hashlib.sha256(artifact_bytes).hexdigest(),
                        len(artifact_bytes),
                        created_at,
                        self._canonical_json(provenance),
                        artifact_bytes,
                    ),
                )
        return run

    def get(self, run_id: UUID) -> LabRunResponse:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload_json FROM lab_runs WHERE run_id = ?",
                (str(run_id),),
            ).fetchone()
        if row is None:
            raise LabRunNotFound(str(run_id))
        try:
            payload: dict[str, Any] = json.loads(row["payload_json"])
            run = LabRunResponse.model_validate(payload)
            self._verify_result_hash(run, payload)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise RuntimeError("Stored lab run failed schema or integrity validation.") from error
        return run

    def list_runs(self, limit: int = 20, offset: int = 0) -> tuple[list[LabRunResponse], int]:
        with closing(self._connect()) as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM lab_runs").fetchone()[0])
            rows = connection.execute(
                "SELECT payload_json FROM lab_runs "
                "ORDER BY created_at DESC, run_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        runs: list[LabRunResponse] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
                run = LabRunResponse.model_validate(payload)
                self._verify_result_hash(run, payload)
                runs.append(run)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                raise RuntimeError(
                    "Stored lab run failed schema or integrity validation."
                ) from error
        return runs, total

    def list_artifacts(self, run_id: UUID) -> list[LabArtifactMetadata]:
        with closing(self._connect()) as connection:
            exists = connection.execute(
                "SELECT 1 FROM lab_runs WHERE run_id = ?", (str(run_id),)
            ).fetchone()
            if exists is None:
                raise LabRunNotFound(str(run_id))
            rows = connection.execute(
                "SELECT * FROM lab_artifacts WHERE run_id = ? ORDER BY created_at, artifact_id",
                (str(run_id),),
            ).fetchall()
        artifacts: list[LabArtifactMetadata] = []
        for row in rows:
            artifact = self.get_artifact(UUID(row["artifact_id"]))
            artifacts.append(
                LabArtifactMetadata.model_validate(artifact.model_dump(exclude={"content"}))
            )
        return artifacts

    def get_artifact(self, artifact_id: UUID) -> LabArtifactResponse:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM lab_artifacts WHERE artifact_id = ?", (str(artifact_id),)
            ).fetchone()
        if row is None:
            raise LabArtifactNotFound(str(artifact_id))
        content_bytes = bytes(row["content_json"])
        if hashlib.sha256(content_bytes).hexdigest() != row["sha256"]:
            raise RuntimeError("Stored lab artifact digest does not match its content.")
        if len(content_bytes) != row["size_bytes"] or len(content_bytes) > _MAX_ARTIFACT_BYTES:
            raise RuntimeError("Stored lab artifact size validation failed.")
        try:
            content = json.loads(content_bytes)
            metadata = self._artifact_metadata(row)
            run = LabRunResponse.model_validate(content)
            self._verify_result_hash(run, content)
            if str(run.run_id) != row["run_id"]:
                raise ValueError("Artifact run ID does not match its provenance.")
            expected_provenance = {
                "run_id": str(run.run_id),
                "title": run.title,
                "status": run.status,
                "configuration_sha256": run.configuration_sha256,
                "result_sha256": run.result_sha256,
                "plan_record_id": str(run.plan_record_id) if run.plan_record_id else None,
                "step_ids": [step.step_id for step in run.steps],
                "artifact_role": "canonical-run-result",
            }
            if metadata.provenance != expected_provenance:
                raise ValueError("Artifact provenance does not match the canonical run record.")
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise RuntimeError(
                "Stored lab artifact provenance, schema, or integrity validation failed."
            ) from error
        return LabArtifactResponse(**metadata.model_dump(), content=content)
