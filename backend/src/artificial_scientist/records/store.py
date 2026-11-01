"""SQLite-backed, append-only research records with provenance and checksums."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from artificial_scientist.records.identity import source_identity_key
from artificial_scientist.records.models import (
    ApprovalRequestRecord,
    ArtifactRecord,
    AuditEventEnvelope,
    ClaimRecord,
    ExperimentPlanRecord,
    ExperimentRunRecord,
    HypothesisRecord,
    KnowledgeConceptRecord,
    KnowledgeRelationshipRecord,
    ManuscriptRecord,
    ModelInvocationRecord,
    RecordBase,
    RecordEnvelope,
    RecordType,
    ResearchTaskRecord,
    ReviewRecord,
    SourceRecord,
)

SCHEMA_VERSION = 3
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
    "knowledge_concept": KnowledgeConceptRecord,
    "knowledge_relationship": KnowledgeRelationshipRecord,
    "manuscript": ManuscriptRecord,
    "model_invocation": ModelInvocationRecord,
}


class RecordStoreError(Exception):
    """Base exception for record-store failures."""


class RecordNotFound(RecordStoreError):
    """Raised when a requested record does not exist."""


class RecordConflict(RecordStoreError):
    """Raised when a new record reuses an existing record ID."""


class DuplicateSource(RecordStoreError):
    """Raised when equivalent source metadata is already stored."""

    def __init__(self, existing_record_id: UUID) -> None:
        self.existing_record_id = existing_record_id
        super().__init__(f"An equivalent source record already exists: {existing_record_id}.")


class InvalidRelationship(RecordStoreError):
    """Raised when a record references a missing or incompatible record."""


class RecordIntegrityError(RecordStoreError):
    """Raised when stored payload bytes or schemas fail integrity checks."""


class UnsupportedDatabaseVersion(RecordStoreError):
    """Raised rather than opening a database from a newer schema version."""


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat()


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


def _source_identity_lookup_key(record: SourceRecord, tenant_id: str | None) -> str:
    identity = source_identity_key(record)
    return identity if tenant_id is None else f"tenant:{tenant_id}:{identity}"


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
        with closing(self._connect()) as connection:
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
                    tenant_id TEXT,
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
                    tenant_id TEXT,
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
                CREATE TABLE IF NOT EXISTS source_identity (
                    identity_key TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    record_id TEXT NOT NULL UNIQUE
                        REFERENCES research_records(id) ON DELETE RESTRICT
                )
                """
            )
            # Schema v3 adds nullable tenant ownership columns. Existing rows are
            # deliberately left NULL: a migration must never guess tenant ownership.
            # Production API access remains fail-closed until scoped operations and
            # an explicit, audited legacy-data assignment workflow are deployed.
            for table in ("research_records", "audit_events", "source_identity"):
                columns = {
                    str(row["name"])
                    for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
                }
                if "tenant_id" not in columns:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN tenant_id TEXT")

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_records_tenant_type_created
                ON research_records(tenant_id, record_type, created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_occurred
                ON audit_events(tenant_id, occurred_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS source_identity_no_update
                BEFORE UPDATE ON source_identity
                BEGIN
                    SELECT RAISE(ABORT, 'source identities are append-only');
                END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS source_identity_no_delete
                BEFORE DELETE ON source_identity
                BEGIN
                    SELECT RAISE(ABORT, 'source identities are append-only');
                END
                """
            )
            # Backfill schema-v1 source records during migration. Preserve existing
            # record history and map duplicate identities to the first record.
            source_rows = connection.execute(
                """
                SELECT id, tenant_id, content_sha256, payload_json
                FROM research_records
                WHERE record_type = 'source'
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
            for source_row in source_rows:
                payload_json = str(source_row["payload_json"])
                if _sha256_text(payload_json) != str(source_row["content_sha256"]):
                    raise RecordIntegrityError(
                        f"Existing source {source_row['id']} failed its checksum during migration."
                    )
                try:
                    source_record = SourceRecord.model_validate_json(payload_json)
                except Exception as exc:
                    raise RecordIntegrityError(
                        f"Existing source {source_row['id']} failed schema validation "
                        "during migration."
                    ) from exc
                connection.execute(
                    "INSERT OR IGNORE INTO source_identity("
                    "identity_key, tenant_id, record_id) VALUES (?, ?, ?)",
                    (
                        _source_identity_lookup_key(
                            source_record, source_row["tenant_id"]
                        ),
                        source_row["tenant_id"],
                        str(source_record.id),
                    ),
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
            if current_version < SCHEMA_VERSION:
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
        elif isinstance(record, KnowledgeConceptRecord):
            add_many(record.source_record_ids, {"source"}, "source_record_ids")
        elif isinstance(record, KnowledgeRelationshipRecord):
            references.extend(
                [
                    (
                        record.source_concept_id,
                        {"knowledge_concept"},
                        "source_concept_id",
                    ),
                    (
                        record.target_concept_id,
                        {"knowledge_concept"},
                        "target_concept_id",
                    ),
                ]
            )
            add_many(
                record.evidence_source_record_ids,
                {"source"},
                "evidence_source_record_ids",
            )
        elif isinstance(record, (ReviewRecord, ApprovalRequestRecord)):
            references.append(
                (
                    record.target_record_id,
                    set(MODEL_BY_TYPE) - {"approval_request"},
                    "target_record_id",
                )
            )

        return references

    def _validate_relationships(
        self,
        connection: sqlite3.Connection,
        record: RecordBase,
        *,
        tenant_id: str | None = None,
    ) -> None:
        for reference_id, allowed_types, field_name in self._references(record):
            row = connection.execute(
                "SELECT record_type, tenant_id FROM research_records WHERE id = ?",
                (str(reference_id),),
            ).fetchone()
            if row is None:
                raise InvalidRelationship(
                    f"{field_name} references record {reference_id}, which does not exist."
                )
            if tenant_id is not None and row["tenant_id"] != tenant_id:
                raise InvalidRelationship(
                    f"{field_name} references a record that is not available in this tenant."
                )
            actual_type = str(row["record_type"])
            if actual_type not in allowed_types:
                allowed = ", ".join(sorted(allowed_types))
                raise InvalidRelationship(
                    f"{field_name} expects record type [{allowed}], "
                    f"but {reference_id} has type '{actual_type}'."
                )

        if isinstance(record, KnowledgeRelationshipRecord):
            if record.source_concept_id == record.target_concept_id:
                raise InvalidRelationship("A concept cannot have a relationship to itself.")
            if record.assertion_status != "rejected" and record.predicate in {
                "broader_than",
                "narrower_than",
                "subclass_of",
                "part_of",
                "prerequisite_of",
            }:
                self._validate_acyclic_relationship(connection, record, tenant_id=tenant_id)

    @staticmethod
    def _validate_acyclic_relationship(
        connection: sqlite3.Connection,
        record: KnowledgeRelationshipRecord,
        *,
        tenant_id: str | None = None,
    ) -> None:
        """Reject cycles within one of the controlled transitive predicates."""
        rows = connection.execute(
            """
            SELECT * FROM research_records
            WHERE record_type = 'knowledge_relationship'
              AND (tenant_id IS ? OR tenant_id = ?)
            """
        , (tenant_id, tenant_id)).fetchall()
        adjacency: dict[UUID, list[UUID]] = {}
        for row in rows:
            envelope = RecordStore._row_to_envelope(row)
            payload = envelope.payload
            if (
                payload.get("predicate") != record.predicate
                or payload.get("assertion_status") == "rejected"
            ):
                continue
            source = UUID(str(payload["source_concept_id"]))
            target = UUID(str(payload["target_concept_id"]))
            adjacency.setdefault(source, []).append(target)

        pending = [record.target_concept_id]
        visited: set[UUID] = set()
        while pending:
            current = pending.pop()
            if current == record.source_concept_id:
                raise InvalidRelationship(
                    f"Adding predicate '{record.predicate}' would create a cycle."
                )
            if current in visited:
                continue
            visited.add(current)
            pending.extend(adjacency.get(current, []))

    def search_knowledge_concepts(
        self,
        *,
        query: str | None = None,
        scientific_domain: str | None = None,
        concept_type: str | None = None,
        concept_status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> tuple[list[RecordEnvelope], int]:
        """Search concept labels, definitions, and aliases with server-side pagination."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        conditions = ["record_type = 'knowledge_concept'"]
        parameters: list[object] = []
        conditions.append("tenant_id IS NULL" if tenant_id is None else "tenant_id = ?")
        if tenant_id is not None:
            parameters.append(tenant_id)
        if query and query.strip():
            pattern = f"%{' '.join(query.split()).casefold()}%"
            conditions.append(
                """
                (
                    lower(json_extract(payload_json, '$.preferred_label')) LIKE ?
                    OR lower(json_extract(payload_json, '$.definition')) LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM json_each(payload_json, '$.aliases') AS alias
                        WHERE lower(alias.value) LIKE ?
                    )
                )
                """
            )
            parameters.extend([pattern, pattern, pattern])
        for field_name, value in (
            ("scientific_domain", scientific_domain),
            ("concept_type", concept_type),
            ("status", concept_status),
        ):
            if value:
                conditions.append(
                    f"json_extract(payload_json, '$.{field_name}') = ?"
                )
                parameters.append(value)

        where = " WHERE " + " AND ".join(conditions)
        with closing(self._connect()) as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM research_records" + where,
                    tuple(parameters),
                ).fetchone()[0]
            )
            rows = connection.execute(
                "SELECT * FROM research_records"
                + where
                + " ORDER BY created_at DESC, id ASC LIMIT ? OFFSET ?",
                (*parameters, limit, offset),
            ).fetchall()
        return [self._row_to_envelope(row) for row in rows], total

    def list_knowledge_relationships(
        self,
        *,
        concept_id: UUID,
        direction: str = "both",
        predicate: str | None = None,
        limit: int = 100,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> tuple[list[RecordEnvelope], int]:
        """List graph assertions incident to a concept, with direction preserved."""
        if direction not in {"incoming", "outgoing", "both"}:
            raise ValueError("direction must be incoming, outgoing, or both")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        source_clause = "json_extract(payload_json, '$.source_concept_id') = ?"
        target_clause = "json_extract(payload_json, '$.target_concept_id') = ?"
        if direction == "outgoing":
            incident_clause = source_clause
        elif direction == "incoming":
            incident_clause = target_clause
        else:
            incident_clause = f"({source_clause} OR {target_clause})"
        conditions = ["record_type = 'knowledge_relationship'", incident_clause]
        parameters: list[object] = [str(concept_id)]
        conditions.append("tenant_id IS NULL" if tenant_id is None else "tenant_id = ?")
        if tenant_id is not None:
            parameters.append(tenant_id)
        if direction == "both":
            parameters.append(str(concept_id))
        if predicate:
            conditions.append("json_extract(payload_json, '$.predicate') = ?")
            parameters.append(predicate)
        where = " WHERE " + " AND ".join(conditions)
        with closing(self._connect()) as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM research_records" + where,
                    tuple(parameters),
                ).fetchone()[0]
            )
            rows = connection.execute(
                "SELECT * FROM research_records"
                + where
                + " ORDER BY created_at DESC, id ASC LIMIT ? OFFSET ?",
                (*parameters, limit, offset),
            ).fetchall()
        return [self._row_to_envelope(row) for row in rows], total

    def create(self, record: RecordBase, *, tenant_id: str | None = None) -> RecordEnvelope:
        """Atomically persist a record and audit event within one tenant."""
        payload_json = _canonical_payload(record)
        content_sha256 = _sha256_text(payload_json)
        created_at = _utc_iso()
        record_id = str(record.id)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if isinstance(record, SourceRecord):
                    lookup_key = _source_identity_lookup_key(record, tenant_id)
                    duplicate = connection.execute(
                        "SELECT record_id FROM source_identity WHERE identity_key = ?",
                        (lookup_key,),
                    ).fetchone()
                    if duplicate is not None:
                        raise DuplicateSource(UUID(str(duplicate["record_id"])))
                self._validate_relationships(connection, record, tenant_id=tenant_id)
                connection.execute(
                    """
                    INSERT INTO research_records
                        (
                            id, tenant_id, record_type, schema_version, created_at,
                            content_sha256, payload_json
                        )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        tenant_id,
                        record.record_type,
                        record.schema_version,
                        created_at,
                        content_sha256,
                        payload_json,
                    ),
                )
                if isinstance(record, SourceRecord):
                    connection.execute(
                        "INSERT INTO source_identity("
                        "identity_key, tenant_id, record_id) VALUES (?, ?, ?)",
                        (lookup_key, tenant_id, record_id),
                    )
                connection.execute(
                    """
                    INSERT INTO audit_events
                        (
                            event_id, tenant_id, occurred_at, action, actor, record_id,
                            record_type, content_sha256
                        )
                    VALUES (?, ?, ?, 'record.created', 'local-api-client', ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        tenant_id,
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

    def create_many(
        self, records: list[RecordBase], *, tenant_id: str | None = None
    ) -> list[RecordEnvelope]:
        """Atomically persist a bounded batch and its audit events within one tenant."""
        if not records:
            raise ValueError("records must not be empty")
        if len(records) > 10:
            raise ValueError("a record batch may contain at most 10 items")
        prepared = [(record, _canonical_payload(record), _utc_iso()) for record in records]
        envelopes: list[RecordEnvelope] = []
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                for record, payload_json, created_at in prepared:
                    record_id = str(record.id)
                    if isinstance(record, SourceRecord):
                        lookup_key = _source_identity_lookup_key(record, tenant_id)
                        duplicate = connection.execute(
                            "SELECT record_id FROM source_identity WHERE identity_key = ?",
                            (lookup_key,),
                        ).fetchone()
                        if duplicate is not None:
                            raise DuplicateSource(UUID(str(duplicate["record_id"])))
                    self._validate_relationships(connection, record, tenant_id=tenant_id)
                    digest = _sha256_text(payload_json)
                    connection.execute(
                        """
                        INSERT INTO research_records
                            (
                                id, tenant_id, record_type, schema_version, created_at,
                                content_sha256, payload_json
                            )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record_id,
                            tenant_id,
                            record.record_type,
                            record.schema_version,
                            created_at,
                            digest,
                            payload_json,
                        ),
                    )
                    if isinstance(record, SourceRecord):
                        connection.execute(
                            "INSERT INTO source_identity("
                            "identity_key, tenant_id, record_id) VALUES (?, ?, ?)",
                            (lookup_key, tenant_id, record_id),
                        )
                    connection.execute(
                        """
                        INSERT INTO audit_events
                            (
                                event_id, tenant_id, occurred_at, action, actor, record_id,
                                record_type, content_sha256
                            )
                        VALUES (?, ?, ?, 'record.created', 'local-api-client', ?, ?, ?)
                        """,
                        (
                            str(uuid4()),
                            tenant_id,
                            created_at,
                            record_id,
                            record.record_type,
                            digest,
                        ),
                    )
                    envelopes.append(
                        RecordEnvelope(
                            id=record.id,
                            record_type=record.record_type,
                            schema_version=record.schema_version,
                            created_at=datetime.fromisoformat(created_at),
                            content_sha256=digest,
                            payload=record.model_dump(mode="json"),
                        )
                    )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            if "research_records.id" in str(exc) or "UNIQUE constraint failed" in str(exc):
                raise RecordConflict("A record in the batch conflicts with existing data.") from exc
            raise RecordStoreError("Could not persist the record batch and audit events.") from exc
        return envelopes

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
            model_type.model_validate_json(payload_json)
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
            # Preserve the exact validated JSON fields covered by the stored digest.
            # This keeps older records stable when optional model fields are added later.
            payload=json.loads(payload_json),
        )

    def get(self, record_id: UUID, *, tenant_id: str | None = None) -> RecordEnvelope:
        """Fetch a record only from the requested tenant namespace."""
        with self._connect() as connection:
            if tenant_id is None:
                row = connection.execute(
                    "SELECT * FROM research_records WHERE id = ? AND tenant_id IS NULL",
                    (str(record_id),),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM research_records WHERE id = ? AND tenant_id = ?",
                    (str(record_id), tenant_id),
                ).fetchone()
        if row is None:
            raise RecordNotFound(f"Record {record_id} was not found.")
        return self._row_to_envelope(row)

    def find_source_by_identity(
        self, record: SourceRecord, *, tenant_id: str | None = None
    ) -> RecordEnvelope | None:
        """Find an existing source with the same identity inside one tenant."""
        identity_key = _source_identity_lookup_key(record, tenant_id)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT record_id FROM source_identity WHERE identity_key = ? AND tenant_id IS ?",
                (identity_key, tenant_id),
            ).fetchone()
        if row is None:
            return None
        return self.get(UUID(str(row["record_id"])), tenant_id=tenant_id)

    def list_records(
        self,
        *,
        record_type: RecordType | None = None,
        limit: int = 20,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> tuple[list[RecordEnvelope], int]:
        """List only records belonging to one tenant (or legacy NULL records)."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        conditions = ["tenant_id IS NULL" if tenant_id is None else "tenant_id = ?"]
        params: list[object] = [] if tenant_id is None else [tenant_id]
        if record_type:
            conditions.append("record_type = ?")
            params.append(record_type)
        where = " WHERE " + " AND ".join(conditions)
        with self._connect() as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM research_records" + where,
                    tuple(params),
                ).fetchone()[0]
            )
            rows = connection.execute(
                "SELECT * FROM research_records"
                + where
                + " ORDER BY created_at DESC, id ASC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [self._row_to_envelope(row) for row in rows], total

    def list_audit_events(
        self, *, limit: int = 20, offset: int = 0, tenant_id: str | None = None
    ) -> tuple[list[AuditEventEnvelope], int]:
        """Return audit events scoped to one tenant."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        tenant_clause = "tenant_id IS NULL" if tenant_id is None else "tenant_id = ?"
        base_params: tuple[object, ...] = () if tenant_id is None else (tenant_id,)
        with self._connect() as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE " + tenant_clause,
                    base_params,
                ).fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT event_id, occurred_at, action, actor, record_id,
                       record_type, content_sha256
                FROM audit_events WHERE """
                + tenant_clause
                + " ORDER BY occurred_at DESC, event_id ASC LIMIT ? OFFSET ?",
                (*base_params, limit, offset),
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
