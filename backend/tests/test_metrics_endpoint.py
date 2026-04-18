"""Tests for the Prometheus ``/metrics`` endpoint token gate.

The endpoint is registered by ``app.core.observability.init_prometheus``
during app start-up.  It returns:

* 404 when ``APP_METRICS_TOKEN`` is unset (feature disabled).
* 404 when a wrong ``X-Metrics-Token`` header is supplied.
* 200 + Prometheus exposition body when the header matches the configured
  token.

The app fixture is shared across the test session, so we flip
``settings.metrics_token`` via monkeypatch rather than spinning up a fresh
app per scenario.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import settings


async def test_metrics_endpoint_404_when_token_unset(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "metrics_token", "")
    resp = await client.get("/metrics")
    assert resp.status_code == 404


async def test_metrics_endpoint_404_when_header_missing(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "metrics_token", "correct-horse-battery")
    resp = await client.get("/metrics")
    assert resp.status_code == 404


async def test_metrics_endpoint_404_when_token_wrong(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "metrics_token", "correct-horse-battery")
    resp = await client.get(
        "/metrics", headers={"X-Metrics-Token": "wrong-token"}
    )
    assert resp.status_code == 404


async def test_metrics_endpoint_200_when_token_matches(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "metrics_token", "correct-horse-battery")
    resp = await client.get(
        "/metrics", headers={"X-Metrics-Token": "correct-horse-battery"}
    )
    assert resp.status_code == 200
    # Prometheus exposition format uses text/plain; version 0.0.4.
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    # Instrumentator always exports the python process collector.
    assert "# HELP" in body or "# TYPE" in body
