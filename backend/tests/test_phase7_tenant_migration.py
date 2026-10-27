"""Regression tests for tenant ownership schema migration."""

import sqlite3

from artificial_scientist.records.store import RecordStore, SCHEMA_VERSION


def test_schema_v3_has_nullable_tenant_columns(tmp_path):
    database = tmp_path / "records.sqlite3"
    RecordStore(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert SCHEMA_VERSION == 3
        for table in ("research_records", "audit_events", "source_identity"):
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            assert "tenant_id" in columns
            assert connection.execute(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NOT NULL").fetchone()[0] == 0
