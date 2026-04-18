"""SlowAPI rate limiter singleton.

Uses in-memory backend for development.  Redis backend is stubbed for prod
but not wired in Phase 3 (Phase 12 will harden).

Import the ``limiter`` singleton in routers:

    from app.core.rate_limiter import limiter

    @router.post("/something")
    @limiter.limit("10/minute")
    async def handler(request: Request, ...):
        ...

The ``app`` must have ``app.state.limiter = limiter`` and the
``SlowAPIMiddleware`` (or ``app.add_exception_handler``) attached.
See ``app.main`` for wiring.
"""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# In test environment, disable rate limiting so tests don't interfere with
# each other via shared in-memory state.
_in_test = os.environ.get("APP_ENVIRONMENT", "dev") == "test"

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    enabled=not _in_test,
)
