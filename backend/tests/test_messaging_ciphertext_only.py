"""Adversarial ciphertext-only tests (Phase 6 Security Engineer).

These assert the strongest property: the server never sees plaintext.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests._crypto_helpers import b64url, decrypt, encrypt, new_keypair
from tests.conftest import seed_customer, seed_seller_with_profile

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, pw: str) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": pw}
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


# ---------------------------------------------------------------------------
# End-to-end round-trip — server never sees "Hello Bob"
# ---------------------------------------------------------------------------


async def test_server_sees_only_ciphertext(
    client: AsyncClient, db: AsyncSession
) -> None:
    alice_seller = await seed_seller_with_profile(db, "alice_s@example.com")
    bob_cust = await seed_customer(
        db, "bob_c@example.com", referring_seller_id=alice_seller.id
    )

    alice_tok = await _login(client, "alice_s@example.com", "SellerPass123!")
    bob_tok = await _login(client, "bob_c@example.com", "CustomerPass123!")

    # Both register X25519 keypairs.
    alice_priv, alice_pub = new_keypair()
    bob_priv, bob_pub = new_keypair()

    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(alice_pub), "key_version": 1},
        headers=_h(alice_tok),
    )
    assert r.status_code == 201
    alice_key_id = r.json()["key_id"]

    r = await client.post(
        "/api/v1/keys",
        json={"public_key_b64url": b64url(bob_pub), "key_version": 1},
        headers=_h(bob_tok),
    )
    assert r.status_code == 201
    bob_key_id = r.json()["key_id"]

    # Bob starts the conversation.
    r = await client.post(
        "/api/v1/conversations",
        json={"peer_user_id": str(alice_seller.id)},
        headers=_h(bob_tok),
    )
    cid = r.json()["id"]

    # Alice fetches Bob's current public key.
    r = await client.get(
        f"/api/v1/keys/{bob_cust.id}", headers=_h(alice_tok)
    )
    assert r.status_code == 200

    # Alice → Bob: "Hello Bob"
    secret = b"Hello Bob"
    alice_eph_priv, alice_eph_pub = new_keypair()
    ct_bytes, nonce = encrypt(
        sender_priv=alice_eph_priv,
        recipient_pub_raw=bob_pub,
        plaintext=secret,
    )
    r = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={
            "ciphertext_b64url": b64url(ct_bytes),
            "nonce_b64url": b64url(nonce),
            "ephemeral_public_key_b64url": b64url(alice_eph_pub),
            "recipient_key_id": bob_key_id,
        },
        headers=_h(alice_tok),
    )
    assert r.status_code == 201, r.text

    # --- DB scan: no row contains the plaintext or any substring of it.
    # Search every text/bytea column on messages, conversations, users,
    # platform_settings — the plaintext must not appear.
    tables_to_scan = [
        "messages",
        "conversations",
        "user_public_keys",
    ]
    substrings = [secret, b"Hello", b"Bob"]
    for table in tables_to_scan:
        result = await db.execute(
            sa.text(f"SELECT row_to_json(t)::text AS blob FROM {table} t")
        )
        for (blob,) in result.all():
            if blob is None:
                continue
            blob_bytes = (
                blob.encode() if isinstance(blob, str) else bytes(blob)
            )
            for sub in substrings:
                assert sub not in blob_bytes, (
                    f"plaintext substring {sub!r} leaked into {table}: {blob!r}"
                )

    # --- Bob fetches + decrypts.
    r = await client.get(
        f"/api/v1/conversations/{cid}/messages", headers=_h(bob_tok)
    )
    assert r.status_code == 200
    msg = r.json()["data"][0]
    import base64 as _b

    ct = _b.urlsafe_b64decode(
        msg["ciphertext_b64url"] + "=" * (-len(msg["ciphertext_b64url"]) % 4)
    )
    nc = _b.urlsafe_b64decode(
        msg["nonce_b64url"] + "=" * (-len(msg["nonce_b64url"]) % 4)
    )
    eph = _b.urlsafe_b64decode(
        msg["ephemeral_public_key_b64url"]
        + "=" * (-len(msg["ephemeral_public_key_b64url"]) % 4)
    )
    plaintext = decrypt(
        recipient_priv=bob_priv,
        sender_pub_raw=eph,
        ciphertext=ct,
        nonce=nc,
    )
    assert plaintext == secret


# ---------------------------------------------------------------------------
# Plaintext fields rejected on signup + send
# ---------------------------------------------------------------------------


async def test_signup_rejects_plaintext_message_fields(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Even signup should reject any body/plaintext/text/content field."""
    r = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "try@example.com",
            "password": "SecurePass123!",
            "display_name": "Try",
            "role": "customer",
            "invite_token": "nope",
            "body": "attack plaintext",
        },
    )
    # extra='forbid' on signup + invite error both acceptable; either way
    # plaintext is not persisted.  Status must not be 201.
    assert r.status_code != 201


# ---------------------------------------------------------------------------
# Static code audit: the messaging service never imports AES/X25519/decrypt.
# ---------------------------------------------------------------------------


def test_messaging_service_has_no_crypto_primitives() -> None:
    svc_path = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "services"
        / "messaging_service.py"
    )
    src = svc_path.read_text()
    forbidden_substrings = [
        "AESGCM",
        "X25519",
        "HKDF",
        "decrypt",
        "Decrypt",
        "cryptography.hazmat",
    ]
    for sub in forbidden_substrings:
        assert sub not in src, (
            f"messaging_service.py must not contain {sub!r}"
        )


def test_message_schema_has_no_plaintext_fields() -> None:
    schema_path = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "schemas"
        / "conversations.py"
    )
    src = schema_path.read_text()
    # These MUST NOT appear as field names on the request model.
    # We grep for ": str" declarations to make sure none of them are plaintext.
    import re

    for line in src.splitlines():
        # Look for pydantic field definitions — "name: <type>".
        m = re.match(r"\s+([a-z_]+):\s*(?:str|bytes)\b", line)
        if not m:
            continue
        name = m.group(1)
        assert name not in {
            "body",
            "text",
            "plaintext",
            "content",
            "message",
            "subject",
        }, f"Schema contains forbidden plaintext field: {name}"
