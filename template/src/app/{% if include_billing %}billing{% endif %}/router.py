"""Billing routers (provider-agnostic). Requires the `db` + `users` + `payments` extras.

Both routers depend on :class:`~app.billing.ports.PaymentsPort` (resolved by
``get_payments_provider`` from ``settings.payments_provider``) — they never name Stripe or
Razorpay, and speak only the normalized :class:`~app.billing.ports.PaymentEvent` /
``SubscriptionState``.

``router`` is org-scoped (mounted under ``/orgs``) and authorised by the caller's membership
in ``{org_id}`` via the tenancy dependency:

    POST   /orgs/{org_id}/billing/checkout-session   start provider checkout (returns a url)
    POST   /orgs/{org_id}/billing/portal-session      open the provider customer portal
    GET    /orgs/{org_id}/billing/subscription        the org's subscription (local, else live)
    DELETE /orgs/{org_id}/billing/subscription        cancel the org's subscription
    GET    /orgs/{org_id}/billing/usage               example route gated by require_feature(...)

``webhook_router`` exposes ``POST /billing/webhook`` — called by the provider, not a user, so
it is NOT org-scoped: it reads the active provider's ``signature_header``, verifies via the
port, dedupes by ``(provider, event_id)`` (idempotency), and syncs the ``Subscription`` row
from normalized subscription-lifecycle events.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.dependencies import require_feature
from app.billing.entitlements import FREE_PLAN
from app.billing.models import ProcessedEvent, Subscription
from app.billing.ports import (
    SUBSCRIPTION_EVENTS,
    PaymentError,
    PaymentEvent,
    PaymentsPort,
    WebhookVerificationError,
)
from app.billing.provider import get_payments_provider
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


async def _get_org(org_id: uuid.UUID, session: AsyncSession) -> Organization:
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.post("/{org_id}/billing/checkout-session", response_model=CheckoutSessionRead)
async def create_checkout_session(
    org_id: uuid.UUID,
    payload: CheckoutSessionCreate,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
    payments: PaymentsPort = Depends(get_payments_provider),
) -> CheckoutSessionRead:
    """Start a checkout for the org's subscription with the active provider."""
    org = await _get_org(org_id, session)
    plan = payload.plan or get_settings().payments_default_plan
    try:
        url = await payments.start_checkout(org, plan)
    except PaymentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    # The adapter may have lazily created a provider customer on the org — persist it.
    await session.commit()
    return CheckoutSessionRead(url=url, provider=payments.name)


@router.post("/{org_id}/billing/portal-session", response_model=PortalSessionRead)
async def create_portal_session(
    org_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
    payments: PaymentsPort = Depends(get_payments_provider),
) -> PortalSessionRead:
    """Open the active provider's customer portal for the org."""
    org = await _get_org(org_id, session)
    url = await payments.open_customer_portal(org)
    await session.commit()  # portal may have lazily created a provider customer
    return PortalSessionRead(url=url)


@router.get("/{org_id}/billing/subscription", response_model=SubscriptionRead)
async def get_subscription(
    org_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
    payments: PaymentsPort = Depends(get_payments_provider),
) -> SubscriptionRead:
    """Return the org's subscription — the locally synced row, or a live provider lookup."""
    result = await session.execute(
        select(Subscription).where(Subscription.organization_id == org_id)
    )
    subscription = result.scalar_one_or_none()
    if subscription is not None:
        return SubscriptionRead(
            organization_id=subscription.organization_id,
            provider=subscription.provider,
            provider_subscription_id=subscription.provider_subscription_id,
            status=subscription.status,
            plan=subscription.plan,
            current_period_end=subscription.current_period_end,
        )
    # No webhook has synced a row yet — ask the provider directly.
    org = await _get_org(org_id, session)
    state = await payments.get_subscription(org)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription for this organization",
        )
    return SubscriptionRead(
        organization_id=org_id,
        provider=payments.name,
        provider_subscription_id=state.subscription_id,
        status=state.status,
        plan=state.plan,
        current_period_end=state.period_end,
    )


@router.delete("/{org_id}/billing/subscription")
async def cancel_subscription(
    org_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
    payments: PaymentsPort = Depends(get_payments_provider),
) -> dict[str, str]:
    """Cancel the org's subscription with the active provider (a no-op if none)."""
    org = await _get_org(org_id, session)
    await payments.cancel(org)
    return {"status": "canceled"}


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


async def _sync_subscription(provider: str, event: PaymentEvent, session: AsyncSession) -> None:
    """Upsert the org's Subscription row from a normalized subscription event."""
    result = await session.execute(
        select(Organization).where(Organization.payments_customer_id == event.customer_ref)
    )
    org = result.scalar_one_or_none()
    if org is None:
        return  # an event for a customer we don't know — nothing to sync

    existing = await session.execute(
        select(Subscription).where(Subscription.organization_id == org.id)
    )
    subscription = existing.scalar_one_or_none()
    if subscription is None:
        session.add(
            Subscription(
                organization_id=org.id,
                provider=provider,
                provider_subscription_id=event.subscription_id or "",
                status=event.status or "",
                plan=event.plan or FREE_PLAN,
                current_period_end=event.period_end,
            )
        )
    else:
        subscription.provider = provider
        subscription.provider_subscription_id = (
            event.subscription_id or subscription.provider_subscription_id
        )
        subscription.status = event.status or subscription.status
        subscription.plan = event.plan or subscription.plan
        subscription.current_period_end = event.period_end


@webhook_router.post("/webhook")
async def payments_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    payments: PaymentsPort = Depends(get_payments_provider),
) -> dict[str, str]:
    """Receive provider events: verify the signature, dedupe by (provider, id), then sync."""
    raw_body = await request.body()
    signature = request.headers.get(payments.signature_header, "")
    try:
        event = payments.verify_webhook(raw_body, signature)
    except WebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        ) from exc

    # Idempotency keyed by (provider, event_id): a replay from any provider is a no-op.
    if await session.get(ProcessedEvent, (payments.name, event.event_id)) is not None:
        return {"status": "duplicate"}
    session.add(
        ProcessedEvent(provider=payments.name, event_id=event.event_id, type=event.event_type)
    )

    if event.event_type in SUBSCRIPTION_EVENTS:
        await _sync_subscription(payments.name, event, session)
    await session.commit()
    return {"status": "ok"}
