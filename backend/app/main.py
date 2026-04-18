"""FastAPI application factory for the Invite-Only Marketplace backend.

Wires up:
- CORS middleware (allow * in dev, configurable in prod)
- SlowAPI rate limiter
- Request-ID middleware (X-Request-ID header)
- Structured JSON logging
- Global exception handler for AppException → error envelope
- FastAPI RequestValidationError → error envelope
- Health endpoint
- Auth and Invites routers under /api/v1

See docs/api-contract.md for the full API specification.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler  # type: ignore[attr-defined]
from slowapi.errors import RateLimitExceeded
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.v1.admin_messages import router as admin_messages_router
from app.api.v1.admin_orders import router as admin_orders_router
from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.invites import router as invites_router
from app.api.v1.keys import router as keys_router
from app.api.v1.orders import router as orders_router
from app.api.v1.products import router as products_router
from app.api.v1.sellers import router as sellers_router
from app.api.v1.stores import router as stores_router
from app.core.exceptions import AppException
from app.core.rate_limiter import limiter
from app.core.scheduler import start_purge_scheduler, stop_purge_scheduler
from app.ws.gateway import handle_ws

# ---------------------------------------------------------------------------
# Logging — structured JSON via stdlib (no SQL echo in production)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("marketplace")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    application = FastAPI(
        title="Marketplace API",
        version="0.1.0",
        description=(
            "Invite-only marketplace REST API. "
            "See docs/api-contract.md for the full specification."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # -----------------------------------------------------------------------
    # Rate limiter
    # -----------------------------------------------------------------------
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # -----------------------------------------------------------------------
    # CORS — allow * in dev; restrict in prod via env
    # -----------------------------------------------------------------------
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Phase 12 will lock down to frontend origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # Request-ID middleware — pure ASGI (avoids BaseHTTPMiddleware task issues)
    # -----------------------------------------------------------------------
    class RequestIDMiddleware:
        """Inject X-Request-ID into every response without BaseHTTPMiddleware."""

        def __init__(self, a: ASGIApp) -> None:
            self.app = a

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] not in ("http", "websocket"):
                await self.app(scope, receive, send)
                return

            headers = dict(scope.get("headers", []))
            request_id = (
                headers.get(b"x-request-id", b"").decode() or str(uuid.uuid4())
            )

            async def send_with_request_id(message: Any) -> None:
                if message["type"] == "http.response.start":
                    headers_list = list(message.get("headers", []))
                    headers_list.append(
                        (b"x-request-id", request_id.encode())
                    )
                    message = {**message, "headers": headers_list}
                await send(message)

            await self.app(scope, receive, send_with_request_id)

    application.add_middleware(RequestIDMiddleware)  # type: ignore[arg-type]

    # -----------------------------------------------------------------------
    # Global exception handlers — error envelope
    # -----------------------------------------------------------------------

    @application.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        """Convert AppException to the standard error envelope."""
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "detail": exc.details,
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Wrap Pydantic 422 errors in the error envelope.

        Pydantic v2 sometimes includes raw exception objects in ``ctx.error``
        when a ``field_validator`` raises ``ValueError``.  Strip those out
        so the response stays JSON-serializable.
        """
        def _sanitize(err: dict) -> dict:
            clean = {}
            for k, v in err.items():
                if k == "ctx" and isinstance(v, dict):
                    clean_ctx = {}
                    for ck, cv in v.items():
                        if isinstance(cv, Exception):
                            clean_ctx[ck] = str(cv)
                        else:
                            clean_ctx[ck] = cv
                    clean[k] = clean_ctx
                elif isinstance(v, Exception):
                    clean[k] = str(v)
                else:
                    clean[k] = v
            return clean

        details = [_sanitize(err) for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": "Request validation failed.",
                    "detail": details,
                }
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all for unhandled exceptions."""
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "detail": None,
                }
            },
        )

    # -----------------------------------------------------------------------
    # Lifespan: start purge scheduler (opt-in via APP_ENABLE_SCHEDULER)
    # -----------------------------------------------------------------------

    @application.on_event("startup")
    async def _startup() -> None:
        start_purge_scheduler()

    @application.on_event("shutdown")
    async def _shutdown() -> None:
        await stop_purge_scheduler()

    # -----------------------------------------------------------------------
    # Health endpoint
    # -----------------------------------------------------------------------

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    # -----------------------------------------------------------------------
    # Routers
    # -----------------------------------------------------------------------
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(invites_router, prefix="/api/v1")
    application.include_router(sellers_router, prefix="/api/v1")
    application.include_router(stores_router, prefix="/api/v1")
    application.include_router(products_router, prefix="/api/v1")
    application.include_router(orders_router, prefix="/api/v1")
    application.include_router(admin_orders_router, prefix="/api/v1")
    application.include_router(keys_router, prefix="/api/v1")
    application.include_router(conversations_router, prefix="/api/v1")
    application.include_router(admin_messages_router, prefix="/api/v1")

    # -----------------------------------------------------------------------
    # WebSocket endpoint
    # -----------------------------------------------------------------------
    @application.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:  # noqa: WPS430
        await handle_ws(websocket)

    return application


app = create_app()
