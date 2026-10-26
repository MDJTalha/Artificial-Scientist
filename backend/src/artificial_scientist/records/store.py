"""SQLite-backed, append-only research records with provenance and checksums."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel

from artificial_scientist.records.models import (
    ApprovalRequestRecord,
    ArtifactRecord,
    AuditEventEnvelope,
    ClaimRecord,
    ExperimentPlanRecord,
    ExperimentRunRecord,
    HypothesisRecord,
    Provenance,
    RecordBase,
    RecordEnvelope,
    RecordType,
    ResearchTaskRecord,
    ReviewRecord,
    SourceRecord,
)

SCHEMA_VERSION = 1
RecordModel = TypeVar("RecordModel", bound=RecordBase)

MODEL_BY_TYPE: dict[str, type[RecordBase]] = {
    "research_task": ResearchTaskRecord,
    "source": SourceRecord,
    "claim": ClaimRecord,
    "hypothesis": HypothesisRecord,
    "experiment_plan": ExperimentPlanRecord,
    "experiment_run": ExperimentRunRecord,
    "artifact": ArtifactRecord,
    "review": ReviewRecord,
    "approval_request": ApprovalRequestRecord,
}


class RecordStoreError(Exception):
    """Base exception for record-store failures."""


class RecordNotFound(RecordStoreError):
    """Raised when a requested record does not exist."""


class RecordConflict(RecordStoreError):
    """Raised when a new record reuses an existing record ID."""


class InvalidRelationship(RecordStoreError):
    """Raised when a record references a missing or incompatible record."""


class RecordIntegrityError(RecordStoreError):
    """Raised when stored payload bytes or schemas fail integrity checks."""


class UnsupportedDatabaseVersion(RecordStoreError):
    """Raised rather than opening a database from a newer schema version."""


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_payload(record: RecordBase) -> str:
    """Serialize a validated model consistently for content addressing."""
    return json.dumps(
        record.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class RecordStore:
    """Append-only SQLite store. Record and audit-event writes are transactional."""

    def __init__(self, database_path: str | Path) -> None:
        raw_path = str(database_path)
        if raw_path == ":memory:":
            raise ValueError(
                "A filesystem database path is required so separate connections share state."
            )
        self.path = Path(raw_path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current_version > SCHEMA_VERSION:
                connection.rollback()
                raise UnsupportedDatabaseVersion(
                    f"Database schema version {current_version} is newer than "
                    f"supported version {SCHEMA_VERSION}."
                )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_records (
                    id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_records_type_created
                ON research_records(record_type, created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action = 'record.created'),
                    actor TEXT NOT NULL CHECK(actor = 'local-api-client'),
                    record_id TEXT NOT NULL REFERENCES research_records(id) ON DELETE RESTRICT,
                    record_type TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_events_occurred
                ON audit_events(occurred_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS research_records_no_update
                BEFORE UPDATE ON research_records
                BEGIN
                    SELECT RAISE(ABORT, 'research records are append-only');
                END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS research_records_no_delete
                BEFORE DELETE ON research_records
                BEGIN
                    SELECT RAISE(ABORT, 'research records are append-only');
                END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'audit events are append-only');
                END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'audit events are append-only');
                END
                """
            )
            if current_version == 0:
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()

    @staticmethod
    def _references(record: RecordBase) -> list[tuple[UUID, set[str], str]]:
        """Return references as (id, allowed record types, field name) tuples."""
        references: list[tuple[UUID, set[str], str]] = []

        def add_many(ids: list[UUID], allowed: set[str], field: str) -> None:
            references.extend((item, allowed, field) for item in ids)

        add_many(
            record.provenance.source_record_ids,
            {"source"},
            "provenance.source_record_ids",
        )

        if isinstance(record, ResearchTaskRecord):
            add_many(
                record.related_record_ids,
                set(MODEL_BY_TYPE),
                "related_record_ids",
            )
        elif isinstance(record, ClaimRecord):
            add_many(record.source_record_ids, {"source"}, "source_record_ids")
            add_many(record.related_claim_ids, {"claim"}, "related_claim_ids")
            add_many(record.supporting_artifact_ids, {"artifact"}, "supporting_artifact_ids")
        elif isinstance(record, HypothesisRecord):
            add_many(record.source_record_ids, {"source"}, "source_record_ids")
            add_many(record.claim_record_ids, {"claim"}, "claim_record_ids")
            if record.supersedes_id is not None:
                references.append(
                    (record.supersedes_id, {"hypothesis"}, "supersedes_id")
                )
        elif isinstance(record, ExperimentPlanRecord):
            references.append(
                (record.hypothesis_record_id, {"hypothesis"}, "hypothesis_record_id")
            )
            add_many(record.source_record_ids, {"source"}, "source_record_ids")
        elif isinstance(record, ExperimentRunRecord):
            references.append((record.plan_record_id, {"experiment_plan"}, "plan_record_id"))
            add_many(
                record.output_artifact_ids,
                {"artifact"},
                "output_artifact_ids",
            )
        elif isinstance(record, ArtifactRecord):
            add_many(
                record.related_record_ids,
                set(MODEL_BY_TYPE),
                "related_record_ids",
            )
        elif isinstance(record, (ReviewRecord, ApprovalRequestRecord)):
            references.append(
                (record.target_record_id, set(MODEL_BY_TYPE) - {"approval_request"}, "target_record_id")
            )

        return references

    def _validate_relationships(
        self, connection: sqlite3.Connection, record: RecordBase
    ) -> None:
        for reference_id, allowed_types, field_name in self._references(record):
            row = connection.execute(
                "SELECT record_type FROM research_records WHERE id = ?",
                (str(reference_id),),
            ).fetchone()
            if row is None:
                raise InvalidRelationship(
                    f"{field_name} references record {reference_id}, which does not exist."
                )
            actual_type = str(row["record_type"])
            if actual_type not in allowed_types:
                allowed = ", ".join(sorted(allowed_types))
                raise InvalidRelationship(
                    f"{field_name} expects record type [{allowed}], "
                    f"but {reference_id} has type '{actual_type}'."
                )

    def create(self, record: RecordBase) -> RecordEnvelope:
        """Atomically persist a validated record and its server-generated audit event."""
        payload_json = _canonical_payload(record)
        content_sha256 = _sha256_text(payload_json)
        created_at = _utc_iso()
        record_id = str(record.id)

        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._validate_relationships(connection, record)
                connection.execute(
                    """
                    INSERT INTO research_records
                        (id, record_type, schema_version, created_at, content_sha256, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        record.record_type,
                        record.schema_version,
                        created_at,
                        content_sha256,
                        payload_json,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO audit_events
                        (event_id, occurred_at, action, actor, record_id, record_type, content_sha256)
                    VALUES (?, ?, 'record.created', 'local-api-client', ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        created_at,
                        record_id,
                        record.record_type,
                        content_sha256,
                    ),
                )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            if "research_records.id" in str(exc) or "UNIQUE constraint failed" in str(exc):
                raise RecordConflict(f"Record {record.id} already exists.") from exc
            raise RecordStoreError("Could not persist the record and audit event.") from exc

        return RecordEnvelope(
            id=record.id,
            record_type=record.record_type,
            schema_version=record.schema_version,
            created_at=datetime.fromisoformat(created_at),
            content_sha256=content_sha256,
            payload=record.model_dump(mode="json"),
        )

    @staticmethod
    def _row_to_envelope(row: sqlite3.Row) -> RecordEnvelope:
        payload_json = str(row["payload_json"])
        expected_hash = str(row["content_sha256"])
        actual_hash = _sha256_text(payload_json)
        if actual_hash != expected_hash:
            raise RecordIntegrityError(
                f"Stored record {row['id']} failed its SHA-256 integrity check."
            )

        record_type = str(row["record_type"])
        model_type = MODEL_BY_TYPE.get(record_type)
        if model_type is None:
            raise RecordIntegrityError(f"Unknown stored record type '{record_type}'.")
        try:
            validated_record = model_type.model_validate_json(payload_json)
        except Exception as exc:
            raise RecordIntegrityError(
                f"Stored record {row['id']} no longer matches its declared schema."
            ) from exc

        return RecordEnvelope(
            id=UUID(str(row["id"])),
            record_type=record_type,  # type: ignore[arg-type]
            schema_version=int(row["schema_version"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            content_sha256=expected_hash,
            payload=validated_record.model_dump(mode="json"),
        )

    def get(self, record_id: UUID) -> RecordEnvelope:
        """Fetch one record and verify both stored bytes and schema."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_records WHERE id = ?",
                (str(record_id),),
            ).fetchone()
        if row is None:
            raise RecordNotFound(f"Record {record_id} was not found.")
        return self._row_to_envelope(row)

    def list_records(
        self,
        *,
        record_type: RecordType | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[RecordEnvelope], int]:
        """List records newest-first, optionally filtered by their validated type."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        where_clause = " WHERE record_type = ?" if record_type else ""
        params: tuple[object, ...] = (record_type,) if record_type else ()
        with self._connect() as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM research_records" + where_clause,
                    params,
                ).fetchone()[0]
            )
            rows = connection.execute(
                "SELECT * FROM research_records"
                + where_clause
                + " ORDER BY created_at DESC, id ASC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()

        return [self._row_to_envelope(row) for row in rows], total

    def list_audit_events(
        self, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[AuditEventEnvelope], int]:
        """Return server-generated record-creation audit events."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        with self._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0])
            rows = connection.execute(
                """
                SELECT event_id, occurred_at, action, actor, record_id, record_type, content_sha256
                FROM audit_events
                ORDER BY occurred_at DESC, event_id ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        events = [
            AuditEventEnvelope(
                event_id=UUID(str(row["event_id"])),
                occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
                action="record.created",
                actor="local-api-client",
                record_id=UUID(str(row["record_id"])),
                record_type=row["record_type"],
                content_sha256=str(row["content_sha256"]),
            )
            for row in rows
        ]
        return events, total
