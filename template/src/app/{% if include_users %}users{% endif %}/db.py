"""fastapi-users database adapter (SQLAlchemy). Requires the `db` + `users` extras."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.users.models import User


async def get_user_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncIterator[SQLAlchemyUserDatabase[User, uuid.UUID]]:
    """FastAPI dependency yielding the user-database adapter for the request session."""
    yield SQLAlchemyUserDatabase(session, User)
