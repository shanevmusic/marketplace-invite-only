"""Shared ORM column mixins.

Apply these to model classes as extra base classes:

    class MyModel(UUIDPKMixin, TimestampMixin, Base):
        __tablename__ = "my_models"
        ...
"""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID


class UUIDPKMixin:
    """Adds a UUID v4 primary key column named ``id``."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` with automatic server-side defaults.

    ``created_at`` is set once on INSERT; ``updated_at`` is refreshed on every
    UPDATE by a ``onupdate`` server default.
    """

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        onupdate=sa.text("now()"),
    )


class SoftDeleteMixin:
    """Adds a nullable ``deleted_at`` column for soft-delete semantics.

    Only apply to entities where the schema explicitly requires soft-delete
    (see docs/schema.md §Soft-delete vs hard-delete policy).  A non-null
    value means the row is logically deleted; queries should filter with
    ``WHERE deleted_at IS NULL`` unless the caller is an admin or a background
    retention job.
    """

    deleted_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        default=None,
    )
