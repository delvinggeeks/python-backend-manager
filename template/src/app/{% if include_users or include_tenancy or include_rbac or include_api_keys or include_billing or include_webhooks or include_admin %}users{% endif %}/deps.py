"""The shared FastAPIUsers instance + auth dependencies. Requires the `db` + `users` extras.

Lives in its own module (not ``__init__``) so the custom auth router can import
``current_active_user`` without a circular import through the package ``__init__``.
"""

from __future__ import annotations

import uuid

from fastapi_users import FastAPIUsers

from app.users.auth import auth_backend
from app.users.manager import get_user_manager
from app.users.models import User

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Dependency: requires a valid (version-current, non-denylisted) JWT belonging to an active user.
current_active_user = fastapi_users.current_user(active=True)
