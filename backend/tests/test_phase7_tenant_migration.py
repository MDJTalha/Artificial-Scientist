"""Regression tests for tenant ownership schema migration."""

import sqlite3

from artificial_scientist.records.store import SCHEMA_VERSION, RecordStore


def test_schema_v3_has_nullable_tenant_columns(tmp_path):
    database = tmp_path / "records.sqlite3"
    RecordStore(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert SCHEMA_VERSION == 3
        for table in ("research_records", "audit_events", "source_identity"):
            columns = {
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table})")
            }
            assert "tenant_id" in columns
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NOT NULL"
            ).fetchone()[0]
            assert count == 0


def test_schema_v2_database_migrates_without_assigning_tenants(tmp_path):
    database = tmp_path / "legacy-records.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE research_records (
                id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE audit_events (
                event_id TEXT PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action = 'record.created'),
                actor TEXT NOT NULL CHECK(actor = 'local-api-client'),
                record_id TEXT NOT NULL REFERENCES research_records(id) ON DELETE RESTRICT,
                record_type TEXT NOT NULL,
                content_sha256 TEXT NOT NULL
            );
            CREATE TABLE source_identity (
                identity_key TEXT PRIMARY KEY,
                record_id TEXT NOT NULL UNIQUE
                    REFERENCES research_records(id) ON DELETE RESTRICT
            );
            PRAGMA user_version = 2;
            """
        )

    RecordStore(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        for table in ("research_records", "audit_events", "source_identity"):
            columns = {
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table})")
            }
            assert "tenant_id" in columns
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NOT NULL"
            ).fetchone()[0]
            assert count == 0
