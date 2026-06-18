"""Pydantic schemas for the object-storage endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PresignedUploadRequest(BaseModel):
    # Caller-facing object key; any tenant prefixing is applied server-side.
    key: str = Field(min_length=1)
    content_type: str | None = None


class PresignedUploadResponse(BaseModel):
    key: str
    url: str
    expires_in: int


class PresignedDownloadResponse(BaseModel):
    key: str
    url: str
    expires_in: int


class StorageObject(BaseModel):
    key: str


class ObjectList(BaseModel):
    objects: list[StorageObject]
