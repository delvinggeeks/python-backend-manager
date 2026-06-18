"""Billing models: subscriptions + processed-webhook bookkeeping. Requires `db` + `users`.

``Subscription`` mirrors the org's Stripe subscription (status / plan / billing period),
synced from ``customer.subscription.*`` webhook events. ``ProcessedStripeEvent`` records
every handled event id so a replayed webhook is an idempotent no-op. The Stripe *customer*
id lives on ``organizations.stripe_customer_id`` (``app.tenancy.models``). Both tables map
onto the shared ``Base`` from ``app.db.models``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

# Same import-ordering guard as app.tenancy.models: load fastapi_users.db before the
# adapter's `generics` submodule, or a circular init silently drops the re-exported GUID.
import fastapi_users.db  # noqa: F401  (import-ordering guard — see comment above)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    # One subscription row per org (unique), kept in sync from webhook events.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Stripe subscription status (active / trialing / past_due / canceled / ...).
    status: Mapped[str] = mapped_column(String(50))
    # Internal entitlements plan key, resolved from the Stripe Price (see entitlements.py).
    plan: Mapped[str] = mapped_column(String(50))
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ProcessedStripeEvent(Base):
    __tablename__ = "processed_stripe_events"

    # The Stripe event id is the natural idempotency key: a replayed event collides on this
    # primary key and is skipped, so webhook handling is exactly-once.
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
