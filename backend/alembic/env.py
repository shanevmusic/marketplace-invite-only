"""Alembic environment configuration.

Supports both offline (SQL script) and online (live DB) migration modes.
Uses the **synchronous** database URL (``psycopg2-binary`` driver) as
required by Alembic's synchronous ``run_migrations_online`` path.

The async engine lives in ``app.db.session``; Alembic only needs a sync
connection for DDL operations.
"""

from __future__ import annotations

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Make the project root importable when running ``alembic`` from the
# /backend directory.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Import settings + ALL models so that Base.metadata is fully populated.
# ---------------------------------------------------------------------------
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402, F401  — registers every model against Base.metadata

# ---------------------------------------------------------------------------
# Alembic Config object (gives access to the .ini file values)
# ---------------------------------------------------------------------------
config = context.config

# Override the SQLAlchemy URL from our settings so we never hard-code creds.
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# Attach Python logging config from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for --autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    In offline mode Alembic emits the SQL script without connecting to the
    database.  Useful for review before applying in production.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live database connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
