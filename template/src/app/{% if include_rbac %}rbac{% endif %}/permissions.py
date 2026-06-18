"""Role hierarchy + permission dependencies for organization memberships.

The model is deliberately small and data-driven so it is easy to extend:

* ``ROLE_RANK`` orders the roles — a higher rank holds every power of the ranks below
  it. Add a role by giving it a rank; ``require_role`` immediately understands it.
* ``SCOPES_BY_ROLE`` maps each role to the coarse permission scopes it is granted
  (cumulative — owner ⊇ admin ⊇ member). ``require_scope`` checks against it.

Both ``require_role`` and ``require_scope`` are dependency *factories*: call them with the
threshold you want and pass the result to ``Depends(...)`` on a route. They build on
``get_current_membership`` (so the caller must belong to ``{org_id}``) and raise 403 when
the caller's role is insufficient.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, status

from app.tenancy.dependencies import get_current_membership
from app.tenancy.models import ADMIN, MEMBER, OWNER, Membership

# Role ranks — higher number = more authority. Extend by adding a role string here.
ROLE_RANK: dict[str, int] = {MEMBER: 1, ADMIN: 2, OWNER: 3}

# Permission scopes granted per role (cumulative up the hierarchy). The strings are an
# application convention; add scopes/roles freely without a schema change.
SCOPES_BY_ROLE: dict[str, set[str]] = {
    MEMBER: {"org:read"},
    ADMIN: {"org:read", "members:write"},
    OWNER: {"org:read", "members:write", "org:admin"},
}


def has_role(membership: Membership, minimum: str) -> bool:
    """True if ``membership.role`` ranks at or above ``minimum`` in ``ROLE_RANK``."""
    return ROLE_RANK.get(membership.role, 0) >= ROLE_RANK.get(minimum, 0)


def role_grants_scope(role: str, scope: str) -> bool:
    """True if ``role`` is granted ``scope`` by ``SCOPES_BY_ROLE``."""
    return scope in SCOPES_BY_ROLE.get(role, set())


def require_role(minimum: str) -> Callable[..., Awaitable[Membership]]:
    """Dependency: require the caller to hold at least ``minimum`` in the org."""

    async def _dep(
        membership: Membership = Depends(get_current_membership),
    ) -> Membership:
        if not has_role(membership, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires the '{minimum}' role or higher",
            )
        return membership

    return _dep


def require_scope(scope: str) -> Callable[..., Awaitable[Membership]]:
    """Dependency: require the caller's role to grant ``scope``."""

    async def _dep(
        membership: Membership = Depends(get_current_membership),
    ) -> Membership:
        if not role_grants_scope(membership.role, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires the '{scope}' permission",
            )
        return membership

    return _dep
