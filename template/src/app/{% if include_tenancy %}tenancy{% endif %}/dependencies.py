"""FastAPI dependencies for tenancy.

``get_current_membership`` resolves the caller's membership in the ``{org_id}`` path
parameter, yielding it for the route or raising 404 if the caller does not belong to the
organization. It is the building block a permissions layer wraps to enforce roles.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.tenancy.models import Membership
from app.users import current_active_user
from app.users.models import User


async def get_current_membership(
    org_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Membership:
    """Return the caller's membership in ``org_id``, or 404 if they don't belong to it."""
    result = await session.execute(
        select(Membership).where(
            Membership.organization_id == org_id,
            Membership.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return membership
