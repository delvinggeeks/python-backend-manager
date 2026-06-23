"""Pydantic schemas for the user resource. Requires the `users` extra."""

from __future__ import annotations

import uuid

from fastapi_users import schemas
from pydantic import BaseModel


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


class TokenPair(BaseModel):
    """Issued at login + on every refresh: a short access token and its rotating refresh token."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105  (OAuth token-type label, not a secret)


class RefreshRequest(BaseModel):
    """Body for ``/auth/jwt/refresh`` and ``/auth/jwt/logout`` — the current refresh token."""

    refresh_token: str
