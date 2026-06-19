"""Users / auth capability built on fastapi-users.

Requires the `db` and `users` extras (`users` == `fastapi-users[sqlalchemy]`).
`app.main.create_app` mounts the register / login / reset / verify / users routers
under `/auth` and `/users`. Protect your own routes with the `current_active_user`
dependency:

    from fastapi import Depends

    from app.users import current_active_user
    from app.users.models import User


    @router.get("/me/items")
    async def my_items(user: User = Depends(current_active_user)) -> list[Item]:
        ...
"""

from __future__ import annotations

import uuid

from fastapi_users import FastAPIUsers

from app.users.auth import auth_backend
from app.users.manager import get_user_manager
from app.users.models import User

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Dependency: requires a valid JWT belonging to an active user.
current_active_user = fastapi_users.current_user(active=True)

__all__ = ["auth_backend", "current_active_user", "fastapi_users"]
