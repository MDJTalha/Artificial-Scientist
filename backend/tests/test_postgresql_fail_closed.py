"""PostgreSQL configuration must never silently fall back to SQLite stores."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from artificial_scientist.api.routes import autonomy, lab, records
from artificial_scientist.lab import retention


@pytest.fixture
def postgres_settings() -> SimpleNamespace:
    return SimpleNamespace(
        database_url="postgresql+psycopg://asds:secret@db.example/asds",
        database_path="data/legacy.sqlite3",
    )


def test_record_store_fails_closed_with_postgresql(monkeypatch, postgres_settings) -> None:
    monkeypatch.setattr(records, "get_settings", lambda: postgres_settings)
    records.get_record_store.cache_clear()
    try:
        with pytest.raises(HTTPException) as error:
            records.get_record_store()
        assert error.value.status_code == 503
        assert "not migrated" in error.value.detail
    finally:
        records.get_record_store.cache_clear()


def test_lab_store_fails_closed_with_postgresql(monkeypatch, postgres_settings) -> None:
    monkeypatch.setattr(lab, "get_settings", lambda: postgres_settings)
    lab.get_lab_store.cache_clear()
    try:
        with pytest.raises(HTTPException) as error:
            lab.get_lab_store()
        assert error.value.status_code == 503
        assert "not migrated" in error.value.detail
    finally:
        lab.get_lab_store.cache_clear()


def test_autonomy_store_fails_closed_with_postgresql(
    monkeypatch, postgres_settings
) -> None:
    monkeypatch.setattr(autonomy, "get_settings", lambda: postgres_settings)
    with pytest.raises(HTTPException) as error:
        autonomy._engine("tenant-1")
    assert error.value.status_code == 503
    assert "not migrated" in error.value.detail


def test_retention_job_fails_closed_with_postgresql(
    monkeypatch, postgres_settings
) -> None:
    monkeypatch.setattr(retention, "get_settings", lambda: postgres_settings)
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_LAB_RETENTION_DAYS", "30")
    with pytest.raises(SystemExit, match="No SQLite fallback is permitted"):
        retention.main()
