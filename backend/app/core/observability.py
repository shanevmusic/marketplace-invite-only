"""Observability wiring — Sentry + Prometheus metrics.

All features are opt-in: Sentry activates only when ``APP_SENTRY_DSN`` is
set; Prometheus is always available but ``/metrics`` is admin-role-gated.

Custom gauges/counters live here so other modules (ws/gateway.py, order
services) import them and increment without re-declaring.

Kept deliberately lightweight — no global side effects at import time.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge

if TYPE_CHECKING:
    from fastapi import FastAPI

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom metrics
# ---------------------------------------------------------------------------

ws_connections_active = Gauge(
    "ws_connections_active",
    "Number of currently-open WebSocket connections.",
)
messages_sent_total = Counter(
    "messages_sent_total",
    "Total encrypted messages successfully delivered.",
    labelnames=("kind",),  # text | image | system
)
orders_placed_total = Counter(
    "orders_placed_total",
    "Total orders successfully placed.",
    labelnames=("currency",),
)


# ---------------------------------------------------------------------------
# Sentry init
# ---------------------------------------------------------------------------


def init_sentry(dsn: str, environment: str, release: str | None = None) -> None:
    """Initialize Sentry if a DSN is configured.

    Called once at application startup.  Safe to call with an empty DSN
    (turns into a no-op).
    """
    if not dsn:
        _logger.info("Sentry disabled: APP_SENTRY_DSN not set")
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        _logger.warning("sentry-sdk not installed; skipping Sentry init")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.0,
        send_default_pii=False,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )
    _logger.info("Sentry initialised for environment=%s", environment)


# ---------------------------------------------------------------------------
# Prometheus instrumentator
# ---------------------------------------------------------------------------


def init_prometheus(app: "FastAPI") -> None:
    """Attach prometheus-fastapi-instrumentator and expose /metrics.

    /metrics is gated behind ``X-Metrics-Token`` matching the configured
    APP_METRICS_TOKEN env var.  An empty token disables the endpoint in
    prod.  Rate-limiter exemption is handled in slowapi config.
    """
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except ImportError:
        _logger.warning("prometheus_fastapi_instrumentator not installed")
        return

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/healthz", "/healthz/ready", "/health", "/metrics"],
    )
    instrumentator.instrument(app)

    from fastapi import Request, Response
    from app.core.config import settings

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        token = request.headers.get("x-metrics-token", "")
        expected = settings.metrics_token
        if not expected or token != expected:
            return Response(status_code=404)
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
