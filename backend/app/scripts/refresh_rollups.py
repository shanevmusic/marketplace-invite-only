"""Refresh the ``seller_sales_rollups`` materialized view (Phase 12).

Intended to be invoked by an external scheduler (CloudWatch Events /
Cloud Scheduler) every 15 minutes in prod.  Uses CONCURRENTLY so the
rollup remains queryable while refreshed.

Run with::

    python -m app.scripts.refresh_rollups
"""

from __future__ import annotations

import asyncio
import logging

import sqlalchemy as sa

from app.db.session import AsyncSessionFactory

_logger = logging.getLogger(__name__)


async def _refresh() -> None:
    async with AsyncSessionFactory() as session:
        # CONCURRENTLY requires a UNIQUE index on the materialized view; if
        # the view doesn't exist we no-op so dev environments don't break.
        try:
            await session.execute(
                sa.text(
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY seller_sales_rollups"
                )
            )
            await session.commit()
            _logger.info("rollups.refresh ok")
        except Exception as exc:  # pragma: no cover
            _logger.warning("rollups.refresh skipped: %s", exc)
            await session.rollback()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_refresh())


if __name__ == "__main__":
    main()
