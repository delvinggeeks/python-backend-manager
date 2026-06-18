"""Async S3 client + object helpers (S3-compatible). Requires the `storage` extra.

``s3_client()`` is the single seam mocked in tests: it builds an aioboto3 S3 client from
settings (endpoint / region / credentials — never hard-coded) so it talks to AWS S3 or any
S3-compatible endpoint. The helpers below open that client per call and return presigned
URLs or bytes, so routes never import aioboto3 directly and tests can monkeypatch
``s3_client`` (and ``_bucket``) with an in-memory fake — no network, no credentials.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3

from app.core.config import get_settings


def _bucket() -> str:
    """Return the configured bucket, or raise — every operation needs one."""
    bucket = get_settings().s3_bucket
    if not bucket:
        raise RuntimeError("S3_BUCKET is not configured")
    return bucket


@asynccontextmanager
async def s3_client() -> AsyncIterator[Any]:
    """Yield an aioboto3 S3 client built from settings. This is the seam tests monkeypatch."""
    settings = get_settings()
    session = aioboto3.Session(
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )
    async with session.client("s3", endpoint_url=settings.s3_endpoint_url) as client:
        yield client


async def put_object(key: str, data: bytes, *, content_type: str | None = None) -> None:
    """Upload bytes to ``key``. Objects are private by default (no public ACL)."""
    extra: dict[str, Any] = {}
    if content_type is not None:
        extra["ContentType"] = content_type
    async with s3_client() as client:
        await client.put_object(Bucket=_bucket(), Key=key, Body=data, **extra)


async def get_object(key: str) -> bytes:
    """Download and return the bytes stored at ``key``."""
    async with s3_client() as client:
        response = await client.get_object(Bucket=_bucket(), Key=key)
        body: bytes = await response["Body"].read()
        return body


async def remove_object(key: str) -> None:
    """Delete ``key`` (idempotent — deleting a missing key is a no-op on S3)."""
    async with s3_client() as client:
        await client.delete_object(Bucket=_bucket(), Key=key)


async def list_keys(prefix: str = "") -> list[str]:
    """Return the stored keys under ``prefix`` (used to scope a tenant's objects)."""
    async with s3_client() as client:
        response = await client.list_objects_v2(Bucket=_bucket(), Prefix=prefix)
    contents = response.get("Contents") or []
    return [item["Key"] for item in contents]


async def presigned_put_url(key: str, *, expires_in: int, content_type: str | None = None) -> str:
    """Return a presigned URL a client can PUT to directly (private object)."""
    params: dict[str, Any] = {"Bucket": _bucket(), "Key": key}
    if content_type is not None:
        params["ContentType"] = content_type
    async with s3_client() as client:
        url: str = await client.generate_presigned_url(
            "put_object", Params=params, ExpiresIn=expires_in
        )
        return url


async def presigned_get_url(key: str, *, expires_in: int) -> str:
    """Return a presigned URL a client can GET from directly."""
    async with s3_client() as client:
        url: str = await client.generate_presigned_url(
            "get_object", Params={"Bucket": _bucket(), "Key": key}, ExpiresIn=expires_in
        )
        return url
