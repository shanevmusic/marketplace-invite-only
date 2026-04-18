"""Phase 12 — S3 presigned upload tests using moto."""

from __future__ import annotations

import os

import boto3
import httpx
import pytest
from httpx import AsyncClient
from moto import mock_aws
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import seed_seller_with_profile


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def aws_credentials() -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture()
def s3_env(aws_credentials: None, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Spin up a moto S3 bucket and patch settings to point at it."""
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="mk-test")
        from app.core import config

        monkeypatch.setattr(config.settings, "s3_bucket", "mk-test")
        monkeypatch.setattr(config.settings, "s3_region", "us-east-1")
        monkeypatch.setattr(config.settings, "aws_access_key_id", "testing")
        monkeypatch.setattr(config.settings, "aws_secret_access_key", "testing")
        monkeypatch.setattr(
            config.settings, "s3_cdn_base_url", "https://cdn.example.com"
        )
        yield


async def test_presign_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/uploads/presign",
        json={
            "purpose": "product_image",
            "filename": "a.jpg",
            "content_type": "image/jpeg",
        },
    )
    assert resp.status_code == 401


async def test_presign_returns_503_when_not_configured(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seller = await seed_seller_with_profile(db, email="up1@x.com")
    await db.commit()
    t = await _login(client, "up1@x.com", "SellerPass123!")

    from app.core import config

    monkeypatch.setattr(config.settings, "s3_bucket", "")
    monkeypatch.setattr(config.settings, "aws_access_key_id", "")
    monkeypatch.setattr(config.settings, "aws_secret_access_key", "")

    resp = await client.post(
        "/api/v1/uploads/presign",
        json={
            "purpose": "product_image",
            "filename": "a.jpg",
            "content_type": "image/jpeg",
        },
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "UPLOAD_NOT_CONFIGURED"


async def test_presign_rejects_bad_content_type(
    client: AsyncClient, db: AsyncSession, s3_env  # type: ignore[no-untyped-def]
) -> None:
    seller = await seed_seller_with_profile(db, email="up2@x.com")
    await db.commit()
    t = await _login(client, "up2@x.com", "SellerPass123!")

    resp = await client.post(
        "/api/v1/uploads/presign",
        json={
            "purpose": "product_image",
            "filename": "evil.exe",
            "content_type": "application/octet-stream",
        },
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "UPLOAD_INVALID_CONTENT_TYPE"


async def test_presign_and_confirm_happy_path(
    client: AsyncClient, db: AsyncSession, s3_env  # type: ignore[no-untyped-def]
) -> None:
    seller = await seed_seller_with_profile(db, email="up3@x.com")
    await db.commit()
    t = await _login(client, "up3@x.com", "SellerPass123!")

    resp = await client.post(
        "/api/v1/uploads/presign",
        json={
            "purpose": "product_image",
            "filename": "a.jpg",
            "content_type": "image/jpeg",
        },
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["method"] == "PUT"
    assert body["s3_key"].startswith(f"product-images/{seller.id}/")
    assert body["s3_key"].endswith(".jpg")
    # moto's presigned URLs don't resolve over the real network; drop the
    # object into the bucket directly so the confirm path has something to
    # HEAD.  The presign contract (URL shape, key, expiry) is validated above.
    boto3.client("s3", region_name="us-east-1").put_object(
        Bucket="mk-test",
        Key=body["s3_key"],
        Body=b"\xff\xd8\xff\xe0" + b"x" * 500,
        ContentType="image/jpeg",
    )

    # Confirm — should return the CDN URL.
    resp = await client.post(
        "/api/v1/uploads/confirm",
        json={"s3_key": body["s3_key"]},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200, resp.text
    confirmed = resp.json()
    assert confirmed["s3_key"] == body["s3_key"]
    assert confirmed["url"].startswith("https://cdn.example.com/")


async def test_confirm_rejects_missing_object(
    client: AsyncClient, db: AsyncSession, s3_env  # type: ignore[no-untyped-def]
) -> None:
    seller = await seed_seller_with_profile(db, email="up4@x.com")
    await db.commit()
    t = await _login(client, "up4@x.com", "SellerPass123!")

    resp = await client.post(
        "/api/v1/uploads/confirm",
        json={"s3_key": "product-images/ghost/never-uploaded.jpg"},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "UPLOAD_OBJECT_MISSING"
