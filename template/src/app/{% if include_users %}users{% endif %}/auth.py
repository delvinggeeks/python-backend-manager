"""JWT bearer authentication backend. Requires the `users` extra.

The signing secret and token lifetime come from settings
(`USERS_JWT_SECRET` / `USERS_JWT_LIFETIME_SECONDS`).
"""

from __future__ import annotations

import uuid

from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)

from app.core.config import get_settings
from app.users.models import User

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy[User, uuid.UUID]:
    settings = get_settings()
    return JWTStrategy(
        secret=settings.users_jwt_secret,
        lifetime_seconds=settings.users_jwt_lifetime_seconds,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
