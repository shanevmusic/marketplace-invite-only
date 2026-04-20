"""Admin analytics + ops endpoint tests (Phase 11)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    seed_admin,
    seed_customer,
    seed_driver,
    seed_seller_with_profile,
)


pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_analytics_overview_shape(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, email="aa1@x.com")
    await seed_seller_with_profile(db, email="sa1@x.com")
    await seed_customer(db, email="ca1@x.com")
    await seed_driver(db, email="da1@x.com")
    await db.commit()
    t = await _login(client, "aa1@x.com", "AdminPass123!")

    resp = await client.get(
        "/api/v1/admin/analytics/overview",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in (
        "total_gmv_minor",
        "orders_count",
        "active_users_24h",
        "active_users_7d",
        "active_users_30d",
        "seller_count",
        "customer_count",
        "driver_count",
        "admin_count",
    ):
        assert key in body
    assert body["seller_count"] >= 1
    assert body["customer_count"] >= 1
    assert body["driver_count"] >= 1


async def test_top_sellers_endpoint(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, email="aa2@x.com")
    await db.commit()
    t = await _login(client, "aa2@x.com", "AdminPass123!")
    resp = await client.get(
        "/api/v1/admin/analytics/top-sellers?limit=5",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    assert "data" in resp.json()


async def test_migration_version(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, email="ao1@x.com")
    await db.commit()
    t = await _login(client, "ao1@x.com", "AdminPass123!")
    resp = await client.get(
        "/api/v1/admin/ops/migration-version",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    # After migration 0008 is applied, version should be 0008
    assert body["version"] == "0008"


async def test_retention_config(client: AsyncClient, db: AsyncSession) -> None:
    await seed_admin(db, email="ao2@x.com")
    await db.commit()
    t = await _login(client, "ao2@x.com", "AdminPass123!")

    resp = await client.get(
        "/api/v1/admin/ops/retention-config",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    assert "message_retention_days" in resp.json()

    resp = await client.post(
        "/api/v1/admin/ops/retention-config",
        json={"message_retention_days": 60},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    assert resp.json()["message_retention_days"] == 60


async def test_non_admin_blocked_across_endpoints(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_customer(db, email="rb@x.com")
    await db.commit()
    t = await _login(client, "rb@x.com", "CustomerPass123!")
    for path in [
        "/api/v1/admin/users",
        "/api/v1/admin/products",
        "/api/v1/admin/analytics/overview",
        "/api/v1/admin/analytics/top-sellers",
        "/api/v1/admin/ops/migration-version",
        "/api/v1/admin/ops/retention-config",
    ]:
        resp = await client.get(
            path, headers={"Authorization": f"Bearer {t}"}
        )
        assert resp.status_code == 403, f"{path}: {resp.status_code}"
