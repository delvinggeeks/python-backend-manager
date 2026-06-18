"""The provider-agnostic payments CORE contract — a hexagonal *port*.

This is the app's-needs interface that the billing router, entitlements, and webhook handler
depend on — never a vendor SDK. Concrete providers (Stripe, Razorpay) live BEHIND it in
``app.billing.adapters`` and are selected at runtime by ``settings.payments_provider`` (see
``app.billing.provider``). The rest of the app speaks only :class:`PaymentsPort` and the
normalized value types below, so swapping the provider touches no application code.

Adding a provider = implement :class:`PaymentsPort` in ``app.billing.adapters`` and register
it in ``app.billing.provider`` (see the Billing section of the service README). The one
provider-specific boundary that remains is the FRONTEND checkout handoff: each provider
returns its own hosted-checkout redirect URL from :meth:`PaymentsPort.start_checkout`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


class WebhookVerificationError(Exception):
    """Raised by an adapter when a webhook signature fails verification.

    Provider-neutral on purpose: the webhook route catches THIS (never a vendor-specific
    error), so a forged event is rejected with ``400`` the same way for every provider.
    """


class PaymentError(Exception):
    """A payment operation cannot proceed for a config/usage reason (e.g. a plan with no
    provider price configured). The router maps it to a ``400`` — provider-neutral."""


# Normalized subscription-lifecycle event types. Every adapter maps its provider's raw event
# names onto exactly one of these, so the router's sync logic stays provider-agnostic.
EVENT_SUBSCRIPTION_CREATED = "subscription.created"
EVENT_SUBSCRIPTION_UPDATED = "subscription.updated"
EVENT_SUBSCRIPTION_DELETED = "subscription.deleted"
EVENT_IGNORED = "ignored"

# The lifecycle events that cause the local Subscription row to be (re)synced.
SUBSCRIPTION_EVENTS = frozenset(
    {EVENT_SUBSCRIPTION_CREATED, EVENT_SUBSCRIPTION_UPDATED, EVENT_SUBSCRIPTION_DELETED}
)


def to_naive_utc(unix_ts: int | None) -> datetime | None:
    """Normalize a provider's unix timestamp to a naive-UTC datetime (how we store periods)."""
    if unix_ts is None:
        return None
    return datetime.fromtimestamp(int(unix_ts), tz=UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class PaymentEvent:
    """A provider-neutral, normalized webhook event.

    ``event_id`` is the provider's idempotency key (paired with the provider name in
    ``ProcessedEvent`` so a replay is a no-op). ``customer_ref`` is the provider's customer
    identifier, used to find the owning org. ``plan`` is already resolved to an INTERNAL
    entitlements plan key (see ``app.billing.entitlements``), never a vendor price/plan id.
    """

    event_id: str
    event_type: str
    subscription_id: str | None = None
    status: str | None = None
    plan: str | None = None
    period_end: datetime | None = None
    customer_ref: str | None = None


@dataclass(frozen=True)
class SubscriptionState:
    """A normalized snapshot of a subscription as the app understands it."""

    subscription_id: str
    status: str
    plan: str
    period_end: datetime | None = None


@runtime_checkable
class BillingAccount(Protocol):
    """The org fields the payments layer needs — a STRUCTURAL contract, so the ORM
    ``Organization`` satisfies it without this core port importing the db/tenancy layer.

    ``payments_customer_id`` is read AND written by adapters (lazy customer creation on first
    checkout); the port-agnostic router owns persistence — it commits the session.
    """

    id: uuid.UUID
    name: str
    payments_customer_id: str | None


@runtime_checkable
class PaymentsPort(Protocol):
    """The payments boundary every provider adapter implements.

    Methods speak the app's domain (an org, an internal plan key) and return normalized
    types — never Stripe/Razorpay objects. ``name`` is the provider's stable key
    (``"stripe"`` / ``"razorpay"``), used to scope idempotency in ``ProcessedEvent``;
    ``signature_header`` is the request header the provider signs its webhooks with, so the
    router can read it without knowing which provider is active.
    """

    name: str
    signature_header: str

    async def start_checkout(self, account: BillingAccount, plan: str) -> str:
        """Begin a subscription checkout for ``account`` on internal ``plan``; return the
        redirect URL the frontend sends the user to (the one provider-specific handoff)."""
        ...

    async def open_customer_portal(self, account: BillingAccount) -> str:
        """Return a URL where the customer can manage their subscription / payment methods."""
        ...

    def verify_webhook(self, raw_body: bytes, signature: str) -> PaymentEvent:
        """Verify ``signature`` over the RAW body and return a normalized :class:`PaymentEvent`.

        Raise :class:`WebhookVerificationError` on a bad/forged signature."""
        ...

    async def get_subscription(self, account: BillingAccount) -> SubscriptionState | None:
        """Fetch the account's current subscription from the provider, normalized; ``None``
        when the account has no provider customer or no subscription yet."""
        ...

    async def cancel(self, account: BillingAccount) -> None:
        """Cancel the account's active subscription with the provider (a no-op if none)."""
        ...
