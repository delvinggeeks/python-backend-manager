"""Billing routers. Requires the `db` + `users` + `payments` extras.

``router`` is org-scoped (mounted under ``/orgs``) and authorised by the caller's
membership in ``{org_id}`` via the tenancy dependency:

    POST /orgs/{org_id}/billing/checkout-session   start Stripe Checkout (returns a url)
    POST /orgs/{org_id}/billing/portal-session      open the Stripe customer portal
    GET  /orgs/{org_id}/billing/subscription        the org's synced subscription
    GET  /orgs/{org_id}/billing/usage               example route gated by require_feature(...)

``webhook_router`` exposes ``POST /billing/webhook`` — called by Stripe, not a user, so it
is NOT org-scoped: it verifies the signature, dedupes by event id (idempotency), and syncs
the ``Subscription`` row from ``customer.subscription.*`` events.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import client
from app.billing.dependencies import require_feature
from app.billing.entitlements import FREE_PLAN
from app.billing.models import ProcessedStripeEvent, Subscription
from app.billing.schemas import (
    CheckoutSessionCreate,
    CheckoutSessionRead,
    PortalSessionRead,
    SubscriptionRead,
)
from app.core.config import get_settings
from app.db.session import get_session
from app.tenancy.dependencies import get_current_membership
from app.tenancy.models import Membership, Organization

router = APIRouter()
webhook_router = APIRouter()

# Stripe subscription-lifecycle events we mirror into the local Subscription row.
_SUBSCRIPTION_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)


async def _get_org(org_id: uuid.UUID, session: AsyncSession) -> Organization:
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


async def _ensure_customer(org: Organization, session: AsyncSession) -> str:
    """Return the org's Stripe customer id, creating the customer on first use."""
    if org.stripe_customer_id is None:
        org.stripe_customer_id = client.create_customer(name=org.name, organization_id=str(org.id))
        await session.commit()
    return org.stripe_customer_id


@router.post("/{org_id}/billing/checkout-session", response_model=CheckoutSessionRead)
async def create_checkout_session(
    org_id: uuid.UUID,
    payload: CheckoutSessionCreate,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> CheckoutSessionRead:
    """Start a Stripe Checkout Session for the org's subscription."""
    org = await _get_org(org_id, session)
    price_id = payload.price_id or get_settings().stripe_default_price_id
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No price_id given and STRIPE_DEFAULT_PRICE_ID is not configured",
        )
    customer_id = await _ensure_customer(org, session)
    checkout = client.create_checkout_session(customer_id=customer_id, price_id=price_id)
    return CheckoutSessionRead(id=checkout["id"], url=checkout["url"])


@router.post("/{org_id}/billing/portal-session", response_model=PortalSessionRead)
async def create_portal_session(
    org_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> PortalSessionRead:
    """Open the Stripe customer portal for the org."""
    org = await _get_org(org_id, session)
    customer_id = await _ensure_customer(org, session)
    portal = client.create_billing_portal_session(customer_id=customer_id)
    return PortalSessionRead(url=portal["url"])


@router.get("/{org_id}/billing/subscription", response_model=SubscriptionRead)
async def get_subscription(
    org_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionRead:
    """Return the org's current subscription, synced from Stripe webhooks."""
    result = await session.execute(
        select(Subscription).where(Subscription.organization_id == org_id)
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription for this organization",
        )
    return SubscriptionRead(
        organization_id=subscription.organization_id,
        stripe_subscription_id=subscription.stripe_subscription_id,
        status=subscription.status,
        plan=subscription.plan,
        current_period_end=subscription.current_period_end,
    )


@router.get("/{org_id}/billing/usage")
async def billing_usage(
    org_id: uuid.UUID,
    _: None = Depends(require_feature("advanced_analytics")),
) -> dict[str, Any]:
    """Example route gated by an entitlement: needs the ``advanced_analytics`` feature."""
    return {
        "organization_id": str(org_id),
        "feature": "advanced_analytics",
        "enabled": True,
    }


def _period_end_to_datetime(value: Any) -> datetime | None:
    """Convert a Stripe unix timestamp to a naive-UTC datetime (matching how we store)."""
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=UTC).replace(tzinfo=None)


async def _sync_subscription(obj: dict[str, Any], session: AsyncSession) -> None:
    """Upsert the org's Subscription row from a Stripe subscription object."""
    customer_id = obj.get("customer")
    result = await session.execute(
        select(Organization).where(Organization.stripe_customer_id == customer_id)
    )
    org = result.scalar_one_or_none()
    if org is None:
        return  # an event for a customer we don't know — nothing to sync

    items = obj.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    plan = get_settings().stripe_price_to_plan.get(price_id, FREE_PLAN) if price_id else FREE_PLAN
    period_end = _period_end_to_datetime(obj.get("current_period_end"))

    existing = await session.execute(
        select(Subscription).where(Subscription.organization_id == org.id)
    )
    subscription = existing.scalar_one_or_none()
    if subscription is None:
        session.add(
            Subscription(
                organization_id=org.id,
                stripe_subscription_id=obj["id"],
                status=obj["status"],
                plan=plan,
                current_period_end=period_end,
            )
        )
    else:
        subscription.stripe_subscription_id = obj["id"]
        subscription.status = obj["status"]
        subscription.plan = plan
        subscription.current_period_end = period_end


@webhook_router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Receive Stripe events: verify the signature, dedupe by id, sync the subscription."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = client.construct_event(payload, signature)
    except client.WebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature",
        ) from exc

    event_id = event["id"]
    # Idempotency: a replayed event id is already recorded -> no-op.
    if await session.get(ProcessedStripeEvent, event_id) is not None:
        return {"status": "duplicate"}
    session.add(ProcessedStripeEvent(id=event_id, type=event["type"]))

    if event["type"] in _SUBSCRIPTION_EVENTS:
        await _sync_subscription(event["data"]["object"], session)
    await session.commit()
    return {"status": "ok"}
