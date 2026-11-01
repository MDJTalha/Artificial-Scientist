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


def test_alembic_schema_and_append_only_guards_are_installed(database_url: str) -> None:
    from sqlalchemy import inspect, text

    from artificial_scientist.database import get_database_engine

    engine = get_database_engine(database_url)
    expected = {
        "research_records",
        "audit_events",
        "source_identity",
        "asds_principals",
        "asds_tenants",
        "asds_memberships",
        "asds_security_audit",
        "alembic_version",
    }
    assert expected.issubset(set(inspect(engine).get_table_names()))

    with engine.connect() as connection:
        triggers = set(
            connection.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE '%_append_only'"
                )
            ).scalars()
        )
    assert {
        "research_records_append_only",
        "audit_events_append_only",
        "source_identity_append_only",
    }.issubset(triggers)
