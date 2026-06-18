"""RBAC: a role hierarchy plus FastAPI permission dependencies over memberships.

Roles are the ``Membership.role`` strings the tenancy module persists; this package adds
an ordering (owner > admin > member, extensible via ``ROLE_RANK``) and the
``require_role`` / ``require_scope`` dependency factories the routers enforce with.
"""

from __future__ import annotations

from app.rbac.permissions import (
    ROLE_RANK,
    SCOPES_BY_ROLE,
    has_role,
    require_role,
    require_scope,
    role_grants_scope,
)

__all__ = [
    "ROLE_RANK",
    "SCOPES_BY_ROLE",
    "has_role",
    "require_role",
    "require_scope",
    "role_grants_scope",
]
