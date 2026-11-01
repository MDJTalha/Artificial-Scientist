"""Tests for PostgreSQL URL validation and engine configuration."""

import pytest

from artificial_scientist.database import (
    DatabaseConfigurationError,
    normalize_postgres_url,
)


def test_normalizes_postgresql_url_to_psycopg_three() -> None:
    normalized = normalize_postgres_url(
        "postgresql://asds:secret@db.example.test:5432/asds?sslmode=require"
    )

    assert normalized.startswith("postgresql+psycopg://")
    assert "db.example.test:5432/asds" in normalized
    assert "sslmode=require" in normalized


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///./asds.sqlite3",
        "mysql://user:password@localhost/asds",
        "postgresql://localhost/asds",
        "not-a-database-url",
    ],
)
def test_rejects_unsupported_or_incomplete_database_urls(database_url: str) -> None:
    with pytest.raises(DatabaseConfigurationError):
        normalize_postgres_url(database_url)
