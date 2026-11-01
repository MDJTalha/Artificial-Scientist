"""PostgreSQL engine lifecycle and connection health checks."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import parse_qs

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


class DatabaseConfigurationError(ValueError):
    """Raised when the configured database URL is unsafe or unsupported."""


def normalize_postgres_url(database_url: str) -> str:
    """Normalize PostgreSQL URLs to the explicitly installed psycopg 3 driver."""
    try:
        url = make_url(database_url)
    except Exception as error:
        raise DatabaseConfigurationError("Database URL is invalid.") from error

    if url.drivername == "postgres":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername != "postgresql+psycopg":
        raise DatabaseConfigurationError("Only PostgreSQL with psycopg 3 is supported.")

    if not url.username or not url.password or not url.host or not url.database:
        raise DatabaseConfigurationError(
            "Database URL must include credentials, host, and database name."
        )
    return url.render_as_string(hide_password=False)


@lru_cache(maxsize=8)
def get_database_engine(database_url: str) -> Engine:
    """Return a bounded, pre-ping PostgreSQL engine for the exact configured URL."""
    normalized_url = normalize_postgres_url(database_url)
    return create_engine(
        normalized_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=1800,
        future=True,
    )


def check_database_connection(database_url: str) -> None:
    """Execute a minimal read-only query and normalize driver failures."""
    try:
        with get_database_engine(database_url).connect() as connection:
            connection.execute(text("SELECT 1"))
    except DatabaseConfigurationError:
        raise
    except SQLAlchemyError as error:
        raise ConnectionError("PostgreSQL health check failed.") from error
