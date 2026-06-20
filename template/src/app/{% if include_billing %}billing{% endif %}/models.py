"""Billing models: subscriptions + processed-webhook bookkeeping. Requires `db` + `users`.

Provider-AGNOSTIC. ``Subscription`` records which ``provider`` owns it plus that provider's
subscription id, status, internal plan, and billing period — synced from normalized
``PaymentEvent``s (see app.billing.router). ``ProcessedEvent`` is keyed by
``(provider, event_id)`` so a replayed webhook from ANY provider is an idempotent no-op. The
provider customer id lives on ``organizations.payments_customer_id`` (``app.tenancy.models``).
Both tables map onto the shared ``Base`` from ``app.db.models``.
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
    """One subscription per org, synced from normalized provider webhook events."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    # One subscription row per org (unique), kept in sync from normalized webhook events.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    # Which payments provider owns this subscription ("stripe" | "razorpay").
    provider: Mapped[str] = mapped_column(String(50))
    # The provider's subscription id (globally unique in practice across providers).
    provider_subscription_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Provider subscription status, normalized to a shared vocabulary (active / trialing /
    # past_due / canceled / ...); entitlements grant only on the active set.
    status: Mapped[str] = mapped_column(String(50))
    # Internal entitlements plan key, resolved by the adapter from the provider's price/plan id.
    plan: Mapped[str] = mapped_column(String(50))
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ProcessedEvent(Base):
    """Webhook idempotency ledger keyed by (provider, event_id) — replays are no-ops."""

    __tablename__ = "processed_events"

    # Composite natural idempotency key: the SAME event id from two providers never collides,
    # and a replayed (provider, event_id) is skipped -> exactly-once webhook handling.
    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
