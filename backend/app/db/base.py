"""SQLAlchemy declarative base.

All ORM models inherit from `Base`.  Import this module (and therefore every
model module that registers against `Base.metadata`) before running
``Base.metadata.create_all()`` or generating Alembic migrations.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base.

    All model classes must inherit from this class.  The metadata object
    attached here is imported by ``alembic/env.py`` for auto-generation.
    """
