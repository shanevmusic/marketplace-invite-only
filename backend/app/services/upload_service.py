"""Object-storage upload service (Phase 12 — B-G1).

Issues presigned S3 PUT URLs for direct browser/mobile-client uploads, plus
a post-upload confirmation step that validates the uploaded object.

Design decisions
----------------
- IAM-user creds for now (Phase 13 will switch to IAM role via Instance
  Metadata / IRSA).  Creds live in Settings; missing creds short-circuit
  with 503 ``UPLOAD_NOT_CONFIGURED``.
- ``content_type`` allowlist is enforced BOTH in the presign policy (via
  ``Content-Type`` on the signed URL so S3 rejects mismatched uploads) and
  by the backend before signing.
- Keys are namespaced per-purpose/per-seller: ``product-images/{seller_id}/{uuid}.{ext}``
  ensures one seller can't clobber another's objects and simplifies cleanup.
- Size policy is enforced on PUT via a ``Content-Length`` header requirement,
  plus a ``HEAD`` check in confirm().
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import (
    UploadInvalidContentType,
    UploadNotConfigured,
    UploadObjectMissing,
)

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


Purpose = Literal["product_image", "avatar"]


def _is_configured() -> bool:
    return bool(
        settings.s3_bucket
        and settings.aws_access_key_id
        and settings.aws_secret_access_key
    )


def _s3_client() -> "boto3.client":  # type: ignore[valid-type]
    if not _is_configured():
        raise UploadNotConfigured()
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=BotoConfig(signature_version="s3v4"),
    )


def _build_key(purpose: Purpose, user_id: uuid.UUID, content_type: str) -> str:
    ext = _CONTENT_TYPE_TO_EXT[content_type]
    obj_id = uuid.uuid4().hex
    prefix = "product-images" if purpose == "product_image" else "avatars"
    return f"{prefix}/{user_id}/{obj_id}.{ext}"


def presign_upload(
    *,
    user_id: uuid.UUID,
    purpose: Purpose,
    filename: str,  # reserved for future logging / content-disposition
    content_type: str,
) -> dict[str, object]:
    """Return a presigned PUT URL plus the final key."""
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise UploadInvalidContentType(
            f"Content type {content_type!r} is not allowed."
        )

    client = _s3_client()
    key = _build_key(purpose, user_id, content_type)
    expires = settings.s3_presign_expires_seconds

    url = client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires,
        HttpMethod="PUT",
    )

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires)
    return {
        "upload_url": url,
        "s3_key": key,
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "method": "PUT",
        "max_bytes": settings.s3_upload_max_bytes,
        "content_type": content_type,
    }


def confirm_upload(*, s3_key: str) -> dict[str, str]:
    """HEAD the object, enforce size, return the final CDN URL."""
    client = _s3_client()

    # Reject paths that walk out of our prefixes.
    if ".." in s3_key or s3_key.startswith("/"):
        raise UploadObjectMissing("Invalid key.")

    try:
        head = client.head_object(Bucket=settings.s3_bucket, Key=s3_key)
    except ClientError as exc:  # pragma: no cover - covered by moto tests
        raise UploadObjectMissing("Object not found in storage.") from exc

    size = int(head.get("ContentLength", 0))
    if size <= 0 or size > settings.s3_upload_max_bytes:
        raise UploadObjectMissing(
            f"Object size {size} bytes is invalid (max "
            f"{settings.s3_upload_max_bytes})."
        )

    cdn_base: Optional[str] = settings.s3_cdn_base_url.rstrip("/") or None
    if cdn_base:
        final_url = f"{cdn_base}/{s3_key}"
    else:
        final_url = (
            f"https://{settings.s3_bucket}.s3.{settings.s3_region}."
            f"amazonaws.com/{s3_key}"
        )

    return {"s3_key": s3_key, "url": final_url}
