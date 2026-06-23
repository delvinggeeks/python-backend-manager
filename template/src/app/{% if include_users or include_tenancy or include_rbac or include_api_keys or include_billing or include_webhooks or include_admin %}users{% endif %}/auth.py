"""JWT bearer authentication backend (versioned + denylist-aware). Requires the `users` extra.

The strategy stamps two extra claims so a token can be revoked before it expires:
  * ``tv`` — the user's ``token_version`` at mint time; a mismatch (bumped by logout-everywhere
    / password reset) rejects the token. DB-backed, so it works with no Redis.
  * ``jti`` — a unique id checked against the best-effort Redis denylist (single-session logout).

The signing secret and access-token lifetime come from settings
(``USERS_JWT_SECRET`` / ``USERS_JWT_LIFETIME_SECONDS``).
"""

from __future__ import annotations

import uuid

import jwt
from fastapi_users import exceptions
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.manager import BaseUserManager

from app.core.config import get_settings
from app.users.denylist import is_jti_denied
from app.users.models import User

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


class VersionedJWTStrategy(JWTStrategy[User, uuid.UUID]):
    """JWTStrategy that stamps ``tv`` + ``jti`` and rejects stale-version / denylisted tokens."""

    async def write_token(self, user: User) -> str:
        """Encode an access token carrying the user's current token-version and a fresh jti."""
        data = {
            "sub": str(user.id),
            "aud": self.token_audience,
            "tv": user.token_version,
            "jti": uuid.uuid4().hex,
        }
        return generate_jwt(data, self.encode_key, self.lifetime_seconds, algorithm=self.algorithm)

    async def read_token(
        self, token: str | None, user_manager: BaseUserManager[User, uuid.UUID]
    ) -> User | None:
        """Decode + validate: signature/expiry, jti not denylisted, version still current."""
        if token is None:
            return None
        try:
            data = decode_jwt(
                token, self.decode_key, self.token_audience, algorithms=[self.algorithm]
            )
        except jwt.PyJWTError:
            return None
        user_id = data.get("sub")
        if user_id is None:
            return None
        jti = data.get("jti")
        if jti is not None and await is_jti_denied(jti):
            return None
        try:
            parsed_id = user_manager.parse_id(user_id)
            user = await user_manager.get(parsed_id)
        except (exceptions.UserNotExists, exceptions.InvalidID):
            return None
        # A token minted before a logout-everywhere / password reset carries an old version.
        if data.get("tv") != user.token_version:
            return None
        return user


def get_jwt_strategy() -> VersionedJWTStrategy:
    """Build the access-token strategy from settings (called per request by the backend)."""
    settings = get_settings()
    return VersionedJWTStrategy(
        secret=settings.users_jwt_secret,
        lifetime_seconds=settings.users_jwt_lifetime_seconds,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
