"""Async SQLAlchemy 2.0 session factory. Requires the `db` extra.

Import errors here are intentional if `db` is not installed — only import this
module from code paths that need the database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_settings = get_settings()
if not _settings.database_url:
    raise RuntimeError("DATABASE_URL is required to use app.db.session")

engine = create_async_engine(_settings.database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: `session: AsyncSession = Depends(get_session)`."""
    async with SessionFactory() as session:
        yield session
