"""SQLAlchemy user + refresh-session models. Requires the `db` + `users` extras.

The `user` table is mapped onto the shared declarative ``Base`` from ``app.db.models`` so a
single ``Base.metadata`` covers every table in the service. ``token_version`` powers
logout-everywhere / password-reset invalidation, and ``RefreshToken`` backs rotating refresh
tokens with reuse detection (see ``app.users.sessions``).

Migrations
----------
Alembic is wired in. The initial migration ships the ``user`` table; ``0007_auth_sessions``
adds ``token_version`` and the ``refresh_tokens`` table. Apply with ``just migrate``
(``alembic upgrade head``); ``migrations/env.py`` imports this module so autogenerate always
sees both tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime

# Same import-ordering guard as app.api_keys.models: load fastapi_users.db before the
# adapter's `generics` submodule, or a circular init silently drops the re-exported GUID.
import fastapi_users.db  # noqa: F401  (import-ordering guard — see comment above)
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import Boolean, ForeignKey, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Application user (fastapi-users base + a token-version stamp)."""

    # Bumped on logout-everywhere and on password reset. Every access token embeds the version
    # it was minted with, so a bump rejects every token issued before it — all at once.
    token_version: Mapped[int] = mapped_column(server_default="0", default=0)


class RefreshToken(Base):
    """A rotating, single-use refresh token, stored only as a hash.

    Tokens form a ``family``: rotating one issues its successor in the same family; presenting an
    already-rotated (``used_at`` set) or revoked token is replay → the whole family is revoked
    (reuse detection). Refresh state lives in the DB (not Redis), so the no-Redis path still
    rotates and revokes correctly.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    # SHA-256 hex digest of the opaque token — the token itself is never persisted.
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # All rotations of one login session share a family id.
    family_id: Mapped[uuid.UUID] = mapped_column(GUID, index=True)
    expires_at: Mapped[datetime] = mapped_column()
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
