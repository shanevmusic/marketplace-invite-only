"""Client-side crypto helpers for Phase 6 tests.

These simulate what a phone client would do: generate X25519 keypairs,
derive a shared secret via ECDH + HKDF, and encrypt/decrypt message
content with AES-256-GCM.

NOTE: This module is used ONLY by tests.  No server code path imports it.
The adversarial ciphertext-only test enforces that the server's messaging
service never imports cryptography, AES, or X25519 primitives.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


HKDF_INFO = b"marketplace-e2e-v1"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def new_keypair() -> tuple[X25519PrivateKey, bytes]:
    """Generate an X25519 keypair and return (priv, raw_public_bytes)."""
    priv = X25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv, pub


def encrypt(
    *,
    sender_priv: X25519PrivateKey,
    recipient_pub_raw: bytes,
    plaintext: bytes,
) -> tuple[bytes, bytes]:
    """Encrypt plaintext with AES-256-GCM using an X25519-derived key.

    Returns (ciphertext, nonce).
    """
    recipient_pub = X25519PublicKey.from_public_bytes(recipient_pub_raw)
    shared = sender_priv.exchange(recipient_pub)
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=HKDF_INFO,
    ).derive(shared)
    nonce = os.urandom(12)
    aes = AESGCM(key)
    ct = aes.encrypt(nonce, plaintext, None)
    return ct, nonce


def decrypt(
    *,
    recipient_priv: X25519PrivateKey,
    sender_pub_raw: bytes,
    ciphertext: bytes,
    nonce: bytes,
) -> bytes:
    """Decrypt with AES-256-GCM using X25519 ECDH."""
    sender_pub = X25519PublicKey.from_public_bytes(sender_pub_raw)
    shared = recipient_priv.exchange(sender_pub)
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=HKDF_INFO,
    ).derive(shared)
    return AESGCM(key).decrypt(nonce, ciphertext, None)
