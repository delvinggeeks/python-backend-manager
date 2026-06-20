"""Pydantic schemas for the billing endpoints (provider-agnostic)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CheckoutSessionCreate(BaseModel):
    """Request to start a hosted-checkout session (optional entitlements plan)."""

    # Internal entitlements plan key to subscribe to (e.g. "pro"); the active provider maps it
    # to its own price/plan id. Falls back to settings.payments_default_plan when omitted.
    plan: str | None = None


class CheckoutSessionRead(BaseModel):
    """The hosted-checkout redirect URL and the provider that issued it."""

    # The provider's hosted-checkout redirect URL — the one provider-specific frontend handoff.
    url: str
    # Which provider issued the URL, so the frontend can pick the right SDK if it needs to.
    provider: str


class PortalSessionRead(BaseModel):
    """The customer-portal redirect URL."""

    url: str


class SubscriptionRead(BaseModel):
    """A subscription's current state: provider, status, plan, and period end."""

    organization_id: uuid.UUID
    provider: str
    provider_subscription_id: str
    status: str
    plan: str
    current_period_end: datetime | None
