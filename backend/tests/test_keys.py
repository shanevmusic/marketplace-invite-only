"""Public-key registry tests (Phase 6, ADR-0009, ADR-0013)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests._crypto_helpers import b64url, new_keypair
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


async def test_register_active_key(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "key_s1@example.com")
    tok = await _login(client, "key_s1@example.com", "SellerPass123!")

    _, pub = new_keypair()
    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(pub), "key_version": 1},
        headers=_h(tok),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user_id"] == str(seller.id)
    assert body["status"] == "active"
    assert body["key_version"] == 1


async def test_rotation_demotes_prior_active(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "key_s2@example.com")
    tok = await _login(client, "key_s2@example.com", "SellerPass123!")

    _, pub1 = new_keypair()
    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(pub1), "key_version": 1},
        headers=_h(tok),
    )
    assert r.status_code == 201
    first_id = r.json()["key_id"]

    _, pub2 = new_keypair()
    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(pub2), "key_version": 2},
        headers=_h(tok),
    )
    assert r.status_code == 201
    second_id = r.json()["key_id"]
    assert r.json()["status"] == "active"

    # /keys/me should show both — exactly one active.
    r = await client.get("/api/v1/keys/me", headers=_h(tok))
    assert r.status_code == 200
    data = r.json()["data"]
    actives = [k for k in data if k["status"] == "active"]
    rotated = [k for k in data if k["status"] == "rotated"]
    assert len(actives) == 1
    assert actives[0]["key_id"] == second_id
    assert len(rotated) == 1
    assert rotated[0]["key_id"] == first_id


async def test_peer_key_fetch_with_eligibility(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "key_s3@example.com")
    cust_ok = await seed_customer(
        db, "key_c_ok@example.com", referring_seller_id=seller.id
    )
    cust_stranger = await seed_customer(db, "key_c_stranger@example.com")

    seller_tok = await _login(client, "key_s3@example.com", "SellerPass123!")
    ok_tok = await _login(client, "key_c_ok@example.com", "CustomerPass123!")
    stranger_tok = await _login(
        client, "key_c_stranger@example.com", "CustomerPass123!"
    )

    _, pub = new_keypair()
    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(pub), "key_version": 1},
        headers=_h(seller_tok),
    )
    assert r.status_code == 201

    # Referred customer can fetch seller's key.
    r = await client.get(
        f"/api/v1/keys/{seller.id}", headers=_h(ok_tok)
    )
    assert r.status_code == 200
    assert r.json()["user_id"] == str(seller.id)

    # Stranger customer → 404 PUBLIC_KEY_NOT_FOUND.
    r = await client.get(
        f"/api/v1/keys/{seller.id}", headers=_h(stranger_tok)
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "PUBLIC_KEY_NOT_FOUND"


async def test_peer_key_self_always_allowed(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "key_s4@example.com")
    tok = await _login(client, "key_s4@example.com", "SellerPass123!")
    _, pub = new_keypair()
    await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(pub), "key_version": 1},
        headers=_h(tok),
    )
    r = await client.get(f"/api/v1/keys/{seller.id}", headers=_h(tok))
    assert r.status_code == 200


async def test_revoke_own_key(client: AsyncClient, db: AsyncSession) -> None:
    await seed_seller_with_profile(db, "key_s5@example.com")
    tok = await _login(client, "key_s5@example.com", "SellerPass123!")
    _, pub = new_keypair()
    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(pub), "key_version": 1},
        headers=_h(tok),
    )
    key_id = r.json()["key_id"]

    r = await client.delete(f"/api/v1/keys/{key_id}", headers=_h(tok))
    assert r.status_code == 204

    r = await client.get("/api/v1/keys/me", headers=_h(tok))
    assert r.status_code == 200
    assert r.json()["data"][0]["status"] == "revoked"


async def test_revoke_other_users_key_returns_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "key_s6@example.com")
    await seed_seller_with_profile(db, "key_s7@example.com")
    tok6 = await _login(client, "key_s6@example.com", "SellerPass123!")
    tok7 = await _login(client, "key_s7@example.com", "SellerPass123!")
    _, pub = new_keypair()
    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(pub), "key_version": 1},
        headers=_h(tok6),
    )
    key_id = r.json()["key_id"]

    # User 7 attempts to revoke user 6's key.
    r = await client.delete(f"/api/v1/keys/{key_id}", headers=_h(tok7))
    assert r.status_code == 404


async def test_invalid_public_key_length_422(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "key_s8@example.com")
    tok = await _login(client, "key_s8@example.com", "SellerPass123!")

    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(b"\x01" * 16), "key_version": 1},
        headers=_h(tok),
    )
    assert r.status_code == 422
