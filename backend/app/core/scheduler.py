"""Background scheduler bootstrap for the purge + auto-complete job.

We use a minimal asyncio task rather than pulling in APScheduler so the
surface area stays small and tests don't accidentally spin up a
scheduler.  The scheduler is opt-in via ``APP_ENABLE_SCHEDULER=true``
and runs the purge job every ``APP_PURGE_INTERVAL_SECONDS`` seconds
(default 3600).

Tests invoke ``run_purge_job`` directly via the admin endpoint — they do
NOT rely on this scheduler running.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from app.db.session import AsyncSessionFactory

logger = logging.getLogger("marketplace.scheduler")

_task: Optional[asyncio.Task[None]] = None


def _enabled() -> bool:
    return os.environ.get("APP_ENABLE_SCHEDULER", "false").lower() in ("1", "true", "yes")


def _interval_seconds() -> int:
    try:
        return int(os.environ.get("APP_PURGE_INTERVAL_SECONDS", "3600"))
    except ValueError:
        return 3600


async def _purge_loop() -> None:
    from app.services.order_service import run_purge_job

    interval = _interval_seconds()
    logger.info("purge scheduler started interval=%ss", interval)
    try:
        while True:
            try:
                async with AsyncSessionFactory() as session:
                    result = await run_purge_job(session)
                    await session.commit()
                    logger.info("purge job result=%s", result)
            except Exception:
                logger.exception("purge job failed")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("purge scheduler stopped")
        raise


def start_purge_scheduler() -> None:
    """Launch the purge loop as a background task if enabled."""
    global _task
    if not _enabled():
        return
    if _task is not None and not _task.done():
        return
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_purge_loop())


async def stop_purge_scheduler() -> None:
    """Cancel the purge loop (idempotent)."""
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
