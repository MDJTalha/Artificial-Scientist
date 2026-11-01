"""Alembic environment configured exclusively for PostgreSQL."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from artificial_scientist.database import normalize_postgres_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv("ARTIFICIAL_SCIENTIST_DATABASE_URL")
if not database_url:
    raise RuntimeError("ARTIFICIAL_SCIENTIST_DATABASE_URL is required for migrations.")

config.set_main_option(
    "sqlalchemy.url", normalize_postgres_url(database_url).replace("%", "%%")
)


def run_migrations_offline() -> None:
    """Run migrations without creating an engine."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a short-lived SQLAlchemy connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
