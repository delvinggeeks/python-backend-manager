"""Users / auth capability built on fastapi-users.

Requires the `db` and `users` extras (`users` == `fastapi-users[sqlalchemy]`).
`app.main.create_app` mounts the custom JWT auth router (login / refresh / logout /
logout-all) plus the register / reset / verify / users routers under `/auth` and `/users`.
Protect your own routes with the `current_active_user` dependency:

    from fastapi import Depends

    from app.users import current_active_user
    from app.users.models import User


    @router.get("/me/items")
    async def my_items(user: User = Depends(current_active_user)) -> list[Item]:
        ...

Sessions are hardened (P3): short access tokens + rotating refresh tokens (reuse detection),
a best-effort Redis denylist for single-session logout, and `token_version`-based
logout-everywhere — see `app.users.sessions` / `app.users.denylist`.
"""

from __future__ import annotations

from app.users.auth import auth_backend
from app.users.deps import current_active_user, fastapi_users
from app.users.router import router as auth_router

__all__ = ["auth_backend", "auth_router", "current_active_user", "fastapi_users"]
