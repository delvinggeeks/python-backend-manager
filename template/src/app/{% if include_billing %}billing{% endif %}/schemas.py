"""Pydantic schemas for the billing endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CheckoutSessionCreate(BaseModel):
    # Stripe Price id to subscribe to; falls back to settings.stripe_default_price_id.
    price_id: str | None = Field(default=None)


class CheckoutSessionRead(BaseModel):
    id: str
    url: str


class PortalSessionRead(BaseModel):
    url: str


class SubscriptionRead(BaseModel):
    organization_id: uuid.UUID
    stripe_subscription_id: str
    status: str
    plan: str
    current_period_end: datetime | None
