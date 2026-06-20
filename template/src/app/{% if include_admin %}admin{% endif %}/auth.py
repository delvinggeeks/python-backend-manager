"""Superuser-only authentication for the sqladmin panel.

Requires the `db` + `users` + `admin` extras. Logins are verified against the ``user`` table
with fastapi-users' own password hashing, and ONLY ACTIVE SUPERUSERS are admitted — the panel
is never mounted open. The validated user id is kept in the signed admin session and re-checked
against the database on every request, so deactivating or demoting a user revokes panel access
on their next click.
"""

from __future__ import annotations

import uuid

from fastapi_users.password import PasswordHelper
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import func, select
from starlette.requests import Request

from app.db.session import SessionFactory
from app.users.models import User

# Key under which the authenticated superuser's id is stored in the (signed) admin session.
_SESSION_KEY = "admin_user_id"
_password_helper = PasswordHelper()


async def _active_superuser_by_id(user_id: str) -> User | None:
    """Load a user by id, returning it only if it is still an active superuser."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return None
    async with SessionFactory() as session:
        user = await session.get(User, uid)
    if user is None or not user.is_active or not user.is_superuser:
        return None
    return user


class AdminAuth(AuthenticationBackend):
    """Gate the sqladmin panel on an active-superuser login."""

    async def login(self, request: Request) -> bool:
        """Verify the login form; admit only active superusers (constant-time on failure)."""
        form = await request.form()
        email = str(form.get("username") or "").strip()
        password = str(form.get("password") or "")
        if not email or not password:
            return False

        async with SessionFactory() as session:
            result = await session.execute(
                select(User).where(func.lower(User.email) == email.lower())
            )
            user = result.scalar_one_or_none()

        # Only active superusers may sign in. Hash unconditionally (even when the account is
        # missing or unprivileged) so response time doesn't leak whether the email exists.
        if user is None or not user.is_active or not user.is_superuser:
            _password_helper.hash(password)
            return False
        verified, _ = _password_helper.verify_and_update(password, user.hashed_password)
        if not verified:
            return False

        request.session[_SESSION_KEY] = str(user.id)
        return True

    async def logout(self, request: Request) -> bool:
        """Clear the admin session."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Re-validate the session's superuser against the DB on every request."""
        user_id = request.session.get(_SESSION_KEY)
        if not user_id:
            return False
        # Re-validate against the database every request so a revoked superuser loses access.
        return await _active_superuser_by_id(str(user_id)) is not None
