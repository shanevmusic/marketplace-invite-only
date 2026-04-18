"""Conversation creation + list + IDOR (Phase 6)."""

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


async def _login(client: AsyncClient, email: str, pw: str) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": pw}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def test_customer_starts_with_referring_seller(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "conv_s1@example.com")
    cust = await seed_customer(
        db, "conv_c1@example.com", referring_seller_id=seller.id
    )
    ct = await _login(client, "conv_c1@example.com", "CustomerPass123!")

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["peer_user_id"] == str(seller.id)
    assert body["unread_count"] == 0


async def test_customer_cannot_start_with_unreferred_seller(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "conv_s2@example.com")
    cust = await seed_customer(db, "conv_c2@example.com")  # no referral
    ct = await _login(client, "conv_c2@example.com", "CustomerPass123!")

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


async def test_customer_cannot_start_with_another_customer(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_customer(db, "conv_c3@example.com")
    c4 = await seed_customer(db, "conv_c4@example.com")
    ct = await _login(client, "conv_c3@example.com", "CustomerPass123!")
    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(c4.id)},
        headers=_h(ct),
    )
    assert r.status_code == 404


async def test_customer_cannot_start_with_driver(
    client: AsyncClient, db: AsyncSession
) -> None:
    drv = await seed_driver(db, "conv_d1@example.com")
    await seed_customer(db, "conv_c5@example.com")
    ct = await _login(client, "conv_c5@example.com", "CustomerPass123!")
    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(drv.id)},
        headers=_h(ct),
    )
    assert r.status_code == 404


async def test_seller_initiates_with_referred_customer(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "conv_s3@example.com")
    cust = await seed_customer(
        db, "conv_c6@example.com", referring_seller_id=seller.id
    )
    st = await _login(client, "conv_s3@example.com", "SellerPass123!")

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(cust.id)},
        headers=_h(st),
    )
    assert r.status_code == 201


async def test_conversation_is_idempotent(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "conv_s4@example.com")
    cust = await seed_customer(
        db, "conv_c7@example.com", referring_seller_id=seller.id
    )
    ct = await _login(client, "conv_c7@example.com", "CustomerPass123!")

    r1 = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    r2 = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


async def test_list_and_get_conversation(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "conv_s5@example.com")
    cust = await seed_customer(
        db, "conv_c8@example.com", referring_seller_id=seller.id
    )
    ct = await _login(client, "conv_c8@example.com", "CustomerPass123!")

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    cid = r.json()["id"]

    r = await client.get("/api/v1/conversations", headers=_h(ct))
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["data"]]
    assert cid in ids

    r = await client.get(f"/api/v1/conversations/{cid}", headers=_h(ct))
    assert r.status_code == 200
    assert r.json()["id"] == cid


async def test_idor_get_conversation_by_stranger_returns_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "conv_s6@example.com")
    cust = await seed_customer(
        db, "conv_c9@example.com", referring_seller_id=seller.id
    )
    stranger = await seed_customer(db, "conv_c10@example.com")

    ct = await _login(client, "conv_c9@example.com", "CustomerPass123!")
    st = await _login(client, "conv_c10@example.com", "CustomerPass123!")

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    cid = r.json()["id"]

    r = await client.get(f"/api/v1/conversations/{cid}", headers=_h(st))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


async def test_admin_can_message_anyone(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, "conv_admin@example.com")
    cust = await seed_customer(db, "conv_c11@example.com")  # unreferred
    at = await _login(client, "conv_admin@example.com", "AdminPass123!")

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(cust.id)},
        headers=_h(at),
    )
    assert r.status_code == 201
