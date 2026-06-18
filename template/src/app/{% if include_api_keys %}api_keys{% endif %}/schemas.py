"""Pydantic schemas for API keys. Requires the `users` extra.

``ApiKeyRead`` is built explicitly from the ORM row (not ``from_attributes``) so the
stored space-separated ``scopes`` string is exposed to clients as a list. ``ApiKeyCreated``
extends it with the one-time ``key`` (the full secret), returned only at creation.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ApiKeyRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_user_id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyRead):
    # The full secret, returned exactly once at creation and never persisted in plaintext.
    key: str


class PrincipalRead(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID | None
    api_key_id: uuid.UUID | None
    scopes: list[str]
    auth_method: str
