"""REST message send/list/read/retention tests (Phase 6)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests._crypto_helpers import b64url, encrypt, new_keypair
from tests.conftest import seed_customer, seed_seller_with_profile

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, pw: str) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": pw}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def _register_key(client, tok, pub):
    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(pub), "key_version": 1},
        headers=_h(tok),
    )
    assert r.status_code == 201
    return r.json()["key_id"]


async def _build_pair(db, suffix: str):
    seller = await seed_seller_with_profile(db, f"msg_s_{suffix}@example.com")
    cust = await seed_customer(
        db, f"msg_c_{suffix}@example.com", referring_seller_id=seller.id
    )
    return seller, cust


async def test_send_and_list_and_read(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, cust = await _build_pair(db, "r1")
    ct = await _login(client, "msg_c_r1@example.com", "CustomerPass123!")
    st = await _login(client, "msg_s_r1@example.com", "SellerPass123!")

    cust_priv, cust_pub = new_keypair()
    seller_priv, seller_pub = new_keypair()
    cust_key_id = await _register_key(client, ct, cust_pub)
    seller_key_id = await _register_key(client, st, seller_pub)

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    cid = r.json()["id"]

    # Customer → Seller message
    sender_eph_priv, sender_eph_pub = new_keypair()
    ct_bytes, nonce = encrypt(
        sender_priv=sender_eph_priv,
        recipient_pub_raw=seller_pub,
        plaintext=b"hello seller",
    )
    r = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={
            "ciphertext_b64url": b64url(ct_bytes),
            "nonce_b64url": b64url(nonce),
            "ephemeral_public_key_b64url": b64url(sender_eph_pub),
            "recipient_key_id": seller_key_id,
        },
        headers=_h(ct),
    )
    assert r.status_code == 201, r.text
    msg_id = r.json()["id"]
    assert r.json()["recipient_key_id"] == seller_key_id

    # Seller lists messages
    r = await client.get(
        f"/api/v1/conversations/{cid}/messages", headers=_h(st)
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == msg_id

    # Seller marks the message read
    r = await client.post(
        f"/api/v1/conversations/{cid}/messages/{msg_id}/read",
        headers=_h(st),
    )
    assert r.status_code == 200
    assert r.json()["read_at"] is not None


async def test_stranger_send_message_returns_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, cust = await _build_pair(db, "r2")
    stranger = await seed_customer(db, "msg_stranger_r2@example.com")
    ct = await _login(client, "msg_c_r2@example.com", "CustomerPass123!")
    stranger_tok = await _login(
        client, "msg_stranger_r2@example.com", "CustomerPass123!"
    )

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    cid = r.json()["id"]

    _, eph_pub = new_keypair()
    r = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={
            "ciphertext_b64url": b64url(b"\x01" * 32),
            "nonce_b64url": b64url(b"\x02" * 12),
            "ephemeral_public_key_b64url": b64url(eph_pub),
        },
        headers=_h(stranger_tok),
    )
    assert r.status_code == 404


async def test_list_messages_by_stranger_returns_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, cust = await _build_pair(db, "r3")
    await seed_customer(db, "msg_stranger_r3@example.com")
    ct = await _login(client, "msg_c_r3@example.com", "CustomerPass123!")
    stranger_tok = await _login(
        client, "msg_stranger_r3@example.com", "CustomerPass123!"
    )
    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    cid = r.json()["id"]
    r = await client.get(
        f"/api/v1/conversations/{cid}/messages", headers=_h(stranger_tok)
    )
    assert r.status_code == 404


async def test_plaintext_field_rejected_422(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, cust = await _build_pair(db, "r4")
    ct = await _login(client, "msg_c_r4@example.com", "CustomerPass123!")
    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    cid = r.json()["id"]

    _, eph_pub = new_keypair()
    for forbidden in ("body", "text", "plaintext", "content", "message"):
        r = await client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={
                "ciphertext_b64url": b64url(b"\x01" * 32),
                "nonce_b64url": b64url(b"\x02" * 12),
                "ephemeral_public_key_b64url": b64url(eph_pub),
                forbidden: "some plaintext",
            },
            headers=_h(ct),
        )
        assert r.status_code == 422, (forbidden, r.text)


async def test_cursor_pagination(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, cust = await _build_pair(db, "r5")
    ct = await _login(client, "msg_c_r5@example.com", "CustomerPass123!")

    _, pub = new_keypair()
    await _register_key(client, ct, pub)

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    cid = r.json()["id"]

    for i in range(5):
        eph_priv, eph_pub = new_keypair()
        ct_bytes, nonce = encrypt(
            sender_priv=eph_priv,
            recipient_pub_raw=pub,
            plaintext=f"msg {i}".encode(),
        )
        r = await client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={
                "ciphertext_b64url": b64url(ct_bytes),
                "nonce_b64url": b64url(nonce),
                "ephemeral_public_key_b64url": b64url(eph_pub),
            },
            headers=_h(ct),
        )
        assert r.status_code == 201

    r = await client.get(
        f"/api/v1/conversations/{cid}/messages?limit=2", headers=_h(ct)
    )
    assert r.status_code == 200
    assert len(r.json()["data"]) == 2
    assert r.json()["next_cursor"] is not None

    cursor = r.json()["next_cursor"]
    r = await client.get(
        f"/api/v1/conversations/{cid}/messages",
        params={"limit": 2, "before": cursor},
        headers=_h(ct),
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 2


async def test_message_send_rate_limit(
    client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    """Rate limit kicks in above 60/min on POST /messages."""
    # Re-enable the limiter for this test only.
    from app.core import rate_limiter

    monkeypatch.setattr(rate_limiter.limiter, "enabled", True)

    seller, cust = await _build_pair(db, "r6")
    ct = await _login(client, "msg_c_r6@example.com", "CustomerPass123!")

    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(seller.id)},
        headers=_h(ct),
    )
    cid = r.json()["id"]

    _, eph_pub = new_keypair()
    payload = {
        "ciphertext_b64url": b64url(b"\x01" * 32),
        "nonce_b64url": b64url(b"\x02" * 12),
        "ephemeral_public_key_b64url": b64url(eph_pub),
    }

    saw_429 = False
    for i in range(70):
        r = await client.post(
            f"/api/v1/conversations/{cid}/messages",
            json=payload,
            headers=_h(ct),
        )
        if r.status_code == 429:
            saw_429 = True
            break
        assert r.status_code == 201, r.text
    assert saw_429
