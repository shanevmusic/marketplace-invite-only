"""Phase 12 — push notifications service-layer tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_device import UserDevice
from app.services import push_service
from tests.conftest import seed_seller_with_profile


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_register_device_idempotent(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, email="dev1@x.com")
    await db.commit()
    t = await _login(client, "dev1@x.com", "SellerPass123!")

    # First registration
    resp = await client.post(
        "/api/v1/devices/register",
        json={"platform": "ios", "token": "APNS-TOKEN-ABC"},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 201
    id1 = resp.json()["id"]

    # Second registration with the same token — idempotent
    resp = await client.post(
        "/api/v1/devices/register",
        json={"platform": "ios", "token": "APNS-TOKEN-ABC"},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == id1


async def test_send_notification_noop_when_unconfigured(
    db: AsyncSession,
) -> None:
    seller = await seed_seller_with_profile(db, email="dev2@x.com")
    device = await push_service.register_device(
        db, seller.id, "android", "FCM-TOKEN-XYZ"
    )
    await db.commit()

    # No FCM key configured → sender is NoopSender → no exception, last_seen updates
    await push_service.send_notification(db, seller.id, "Hi", "there")

    await db.refresh(device)
    assert device.last_seen_at is not None
    assert device.disabled_at is None


async def test_send_notification_on_user_with_no_devices_is_noop(
    db: AsyncSession,
) -> None:
    seller = await seed_seller_with_profile(db, email="dev3@x.com")
    await db.commit()

    # Does not raise; silently returns.
    await push_service.send_notification(
        db, seller.id, "Hi", "there", data={"k": "v"}
    )


async def test_register_device_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/devices/register",
        json={"platform": "ios", "token": "x"},
    )
    assert resp.status_code == 401
