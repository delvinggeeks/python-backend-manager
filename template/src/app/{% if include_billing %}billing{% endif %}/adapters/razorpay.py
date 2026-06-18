"""Razorpay adapter behind the :class:`~app.billing.ports.PaymentsPort` (India-first provider).

Wraps the official ``razorpay`` SDK: Subscriptions for checkout (the hosted ``short_url`` is
the redirect), Customers for the billing account, and ``utility.verify_webhook_signature``
(HMAC-SHA256 hex over the raw body) for webhooks. Maps Razorpay's event names, statuses, and
subscription entity onto the normalized ``PaymentEvent`` / ``SubscriptionState`` so the app
never imports ``razorpay``. The client is an injectable seam so tests run with a fake — no
live calls. Plan resolution uses ``settings.razorpay_plan_to_plan_id`` (internal plan ->
Razorpay Plan id), inverted for webhook plan_id -> plan.

Razorpay puts no event id in the webhook body (only the ``X-Razorpay-Event-Id`` header), so a
stable idempotency key is synthesized from the body — replays carry an identical body and
therefore dedupe correctly.
"""

from __future__ import annotations

import json
from typing import Any

import razorpay
from razorpay.errors import SignatureVerificationError

from app.billing.entitlements import FREE_PLAN
from app.billing.ports import (
    EVENT_IGNORED,
    EVENT_SUBSCRIPTION_CREATED,
    EVENT_SUBSCRIPTION_DELETED,
    EVENT_SUBSCRIPTION_UPDATED,
    BillingAccount,
    PaymentError,
    PaymentEvent,
    SubscriptionState,
    WebhookVerificationError,
    to_naive_utc,
)
from app.core.config import Settings, get_settings

# Razorpay subscription event names -> normalized event types. `activated` is the first
# active state (treated as create); terminal states map to delete; the rest are updates.
_EVENT_MAP = {
    "subscription.activated": EVENT_SUBSCRIPTION_CREATED,
    "subscription.authenticated": EVENT_SUBSCRIPTION_UPDATED,
    "subscription.charged": EVENT_SUBSCRIPTION_UPDATED,
    "subscription.updated": EVENT_SUBSCRIPTION_UPDATED,
    "subscription.pending": EVENT_SUBSCRIPTION_UPDATED,
    "subscription.halted": EVENT_SUBSCRIPTION_UPDATED,
    "subscription.paused": EVENT_SUBSCRIPTION_UPDATED,
    "subscription.resumed": EVENT_SUBSCRIPTION_UPDATED,
    "subscription.cancelled": EVENT_SUBSCRIPTION_DELETED,
    "subscription.completed": EVENT_SUBSCRIPTION_DELETED,
    "subscription.expired": EVENT_SUBSCRIPTION_DELETED,
}


def _normalize_status(status: str | None) -> str | None:
    """Map Razorpay's status spelling onto the shared vocabulary entitlements understands."""
    if status is None:
        return None
    s = str(status).lower()
    return "canceled" if s == "cancelled" else s


class RazorpayAdapter:
    """``PaymentsPort`` implementation for Razorpay."""

    name = "razorpay"
    signature_header = "x-razorpay-signature"

    def __init__(self, *, client: Any = None, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # Injectable SDK seam; built from settings when not supplied. Construction does no I/O.
        self._client: Any = client or razorpay.Client(
            auth=(self._settings.razorpay_key_id or "", self._settings.razorpay_key_secret or "")
        )

    # --- plan <-> plan_id mapping ----------------------------------------
    def _plan_to_plan_id(self, plan: str) -> str:
        plan_id = self._settings.razorpay_plan_to_plan_id.get(plan)
        if not plan_id:
            raise PaymentError(f"No Razorpay plan configured for plan {plan!r}")
        return plan_id

    def _plan_id_to_plan(self, plan_id: str | None) -> str:
        if not plan_id:
            return FREE_PLAN
        for plan, pid in self._settings.razorpay_plan_to_plan_id.items():
            if pid == plan_id:
                return plan
        return FREE_PLAN

    # --- customer lifecycle ----------------------------------------------
    def _ensure_customer(self, account: BillingAccount) -> str:
        existing = account.payments_customer_id
        if existing is not None:
            return existing
        customer = self._client.customer.create(
            {"name": account.name, "notes": {"organization_id": str(account.id)}}
        )
        customer_id: str = customer["id"]
        account.payments_customer_id = customer_id
        return customer_id

    # --- PaymentsPort ----------------------------------------------------
    async def start_checkout(self, account: BillingAccount, plan: str) -> str:
        plan_id = self._plan_to_plan_id(plan)
        customer_id = self._ensure_customer(account)
        subscription = self._client.subscription.create(
            {
                "plan_id": plan_id,
                "customer_id": customer_id,
                "total_count": self._settings.razorpay_total_count,
                "customer_notify": 1,
                "notes": {"organization_id": str(account.id)},
            }
        )
        url: str = subscription["short_url"]
        return url

    async def open_customer_portal(self, account: BillingAccount) -> str:
        # Razorpay has no Stripe-style hosted portal; return the configured management URL.
        return self._settings.razorpay_portal_url

    def verify_webhook(self, raw_body: bytes, signature: str) -> PaymentEvent:
        secret = self._settings.razorpay_webhook_secret or ""
        try:
            self._client.utility.verify_webhook_signature(
                raw_body.decode("utf-8"), signature, secret
            )
        except SignatureVerificationError as exc:
            raise WebhookVerificationError(str(exc)) from exc
        return self._to_payment_event(json.loads(raw_body))

    def _to_payment_event(self, event: dict[str, Any]) -> PaymentEvent:
        name = event.get("event", "")
        entity = event.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = entity.get("id")
        created_at = event.get("created_at")
        # No event id in the body -> synthesize a replay-stable idempotency key.
        event_id = f"{name}:{subscription_id}:{created_at}"
        return PaymentEvent(
            event_id=event_id,
            event_type=_EVENT_MAP.get(name, EVENT_IGNORED),
            subscription_id=subscription_id,
            status=_normalize_status(entity.get("status")),
            plan=self._plan_id_to_plan(entity.get("plan_id")),
            period_end=to_naive_utc(entity.get("current_end")),
            customer_ref=entity.get("customer_id"),
        )

    async def get_subscription(self, account: BillingAccount) -> SubscriptionState | None:
        if account.payments_customer_id is None:
            return None
        result = self._client.subscription.all(
            {"customer_id": account.payments_customer_id, "count": 1}
        )
        items = result.get("items", [])
        if not items:
            return None
        sub = items[0]
        return SubscriptionState(
            subscription_id=sub["id"],
            status=_normalize_status(sub.get("status")) or "unknown",
            plan=self._plan_id_to_plan(sub.get("plan_id")),
            period_end=to_naive_utc(sub.get("current_end")),
        )

    async def cancel(self, account: BillingAccount) -> None:
        state = await self.get_subscription(account)
        if state is None:
            return
        self._client.subscription.cancel(state.subscription_id)
