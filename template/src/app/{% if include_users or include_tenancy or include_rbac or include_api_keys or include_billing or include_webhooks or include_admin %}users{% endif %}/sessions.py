"""Rotating refresh-token sessions with reuse detection. Requires the `db` + `users` extras.

A refresh token is an opaque, high-entropy string handed to the client once; only its SHA-256
hash is stored. ``/auth/jwt/refresh`` rotates it — the presented token is marked used and a
successor is minted in the *same family*. Presenting an already-used or revoked token is replay
(token theft), which revokes the whole family and forces a fresh login. All state lives in the
DB, so rotation and revocation work with no Redis.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.users.models import RefreshToken


class RefreshError(Exception):
    """A presented refresh token is unknown, expired, or replayed (reuse detected)."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utcnow() -> datetime:
    # Naive UTC to match the DB columns (which store naive timestamps).
    return datetime.now(UTC).replace(tzinfo=None)


async def issue_refresh_token(
    session: AsyncSession, user_id: uuid.UUID, *, family_id: uuid.UUID | None = None
) -> str:
    """Mint a refresh token (a new family, or the next link in ``family_id``).

    Returns the plaintext token — persisted only as a hash, so it's recoverable exactly once.
    """
    settings = get_settings()
    token = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash(token),
            family_id=family_id or uuid.uuid4(),
            expires_at=_utcnow() + timedelta(seconds=settings.users_refresh_lifetime_seconds),
        )
    )
    await session.flush()
    return token


async def rotate_refresh_token(session: AsyncSession, token: str) -> tuple[uuid.UUID, str]:
    """Validate + rotate a refresh token, returning ``(user_id, new_token)``.

    Raises :class:`RefreshError` if the token is unknown, expired, or replayed; a replay of a
    spent/revoked token revokes the entire family (assume the token was stolen).
    """
    token_hash = _hash(token)
    row = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if row is None:
        raise RefreshError("unknown refresh token")
    if row.expires_at <= _utcnow():
        raise RefreshError("refresh token expired")
    # Atomically CLAIM the token: flip used_at from NULL in a single conditional UPDATE. This is
    # the serialization point — concurrent requests presenting the same token race here and only
    # ONE can match (on Postgres the losers block, then re-check the committed row and match zero
    # rows). So a stolen-token replay / double-spend can't slip through a check-then-set window.
    claimed_id = (
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.used_at.is_(None),
                RefreshToken.revoked.is_(False),
            )
            .values(used_at=_utcnow())
            .returning(RefreshToken.id)
        )
    ).scalar_one_or_none()
    if claimed_id is None:
        # Already spent or revoked → replay (assume theft): revoke the whole family.
        await _revoke_family(session, row.family_id)
        raise RefreshError("refresh token reuse detected")
    new_token = await issue_refresh_token(session, row.user_id, family_id=row.family_id)
    return row.user_id, new_token


async def revoke_family_of(session: AsyncSession, token: str) -> None:
    """Revoke the family of a presented refresh token (single-session logout). No-op if unknown."""
    row = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == _hash(token)))
    ).scalar_one_or_none()
    if row is not None:
        await _revoke_family(session, row.family_id)


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken).where(RefreshToken.family_id == family_id).values(revoked=True)
    )


async def revoke_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every refresh family for a user (logout-everywhere / password reset)."""
    await session.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
    )
