"""Real PostgreSQL smoke tests, executed by the dedicated CI service job."""

import os

import pytest
from fastapi.testclient import TestClient

from artificial_scientist.config import get_settings
from artificial_scientist.database import check_database_connection, get_database_engine
from artificial_scientist.main import app


@pytest.fixture
def database_url() -> str:
    value = os.getenv("ARTIFICIAL_SCIENTIST_DATABASE_URL")
    if not value:
        pytest.skip("PostgreSQL service URL is not configured.")
    return value


def test_postgresql_driver_executes_read_only_health_query(database_url: str) -> None:
    check_database_connection(database_url)


def test_postgresql_engine_uses_bounded_pool(database_url: str) -> None:
    engine = get_database_engine(database_url)

    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 5
    assert engine.pool._pre_ping is True


def test_readiness_reports_postgresql_connected(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_ENV", "production")
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        response = TestClient(app).get("/api/v1/ready")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["scope"] == "postgresql"
    assert response.json()["database"] == "connected"
