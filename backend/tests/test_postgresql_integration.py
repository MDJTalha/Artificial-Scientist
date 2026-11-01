"""Real PostgreSQL smoke tests, executed by the dedicated CI service job."""

import os

import pytest
from fastapi.testclient import TestClient

from artificial_scientist.database import check_database_connection
from artificial_scientist.main import app


@pytest.fixture
def database_url() -> str:
    value = os.getenv("ARTIFICIAL_SCIENTIST_DATABASE_URL")
    if not value:
        pytest.skip("PostgreSQL service URL is not configured.")
    return value


def test_postgresql_driver_executes_read_only_health_query(database_url: str) -> None:
    check_database_connection(database_url)


def test_readiness_reports_postgresql_connected(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_ENV", "production")
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_DATABASE_URL", database_url)

    response = TestClient(app).get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["scope"] == "postgresql"
    assert response.json()["database"] == "connected"
