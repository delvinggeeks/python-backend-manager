"""User manager — registration / password-reset / verification hooks.

Requires the `db` + `users` extras.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Depends
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase

from app.core.config import get_settings
from app.users.db import get_user_db
from app.users.models import User

_settings = get_settings()


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = _settings.users_jwt_secret
    verification_token_secret = _settings.users_jwt_secret


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase[User, uuid.UUID] = Depends(get_user_db),
) -> AsyncIterator[UserManager]:
    """FastAPI dependency yielding the user manager for the request."""
    yield UserManager(user_db)
