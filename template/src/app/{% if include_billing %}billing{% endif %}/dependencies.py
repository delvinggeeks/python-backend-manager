"""Entitlement guards. Requires the `db` + `users` + `payments` extras.

``require_feature("x")`` is a FastAPI dependency factory: it resolves the caller's
membership in the path's ``{org_id}`` (reusing the tenancy dependency), loads the org's
subscription, maps its plan to features, and raises ``403`` unless the plan grants ``x``.
An org with no *active* subscription is treated as the free tier.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.entitlements import ACTIVE_STATUSES, FREE_PLAN, plan_has_feature
from app.billing.models import Subscription
from app.db.session import get_session
from app.tenancy.dependencies import get_current_membership
from app.tenancy.models import Membership


def require_feature(feature: str) -> Callable[..., Awaitable[None]]:
    """Build a dependency that allows the request only if the org's plan grants ``feature``."""

    async def _guard(
        membership: Membership = Depends(get_current_membership),
        session: AsyncSession = Depends(get_session),
    ) -> None:
        result = await session.execute(
            select(Subscription).where(Subscription.organization_id == membership.organization_id)
        )
        subscription = result.scalar_one_or_none()
        plan = (
            subscription.plan
            if subscription is not None and subscription.status in ACTIVE_STATUSES
            else FREE_PLAN
        )
        if not plan_has_feature(plan, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your plan does not include the '{feature}' feature",
            )

    return _guard
