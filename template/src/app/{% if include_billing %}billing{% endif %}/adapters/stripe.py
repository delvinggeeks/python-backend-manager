"""Stripe adapter behind the :class:`~app.billing.ports.PaymentsPort`.

Ports the original thin Stripe-client logic into the port shape. Reads credentials from
settings at call time (test-mode keys via env, never hard-coded) and maps Stripe
Checkout / Billing-Portal / Subscription / Webhook objects onto the normalized
``PaymentEvent`` / ``SubscriptionState`` — so the rest of the app never imports ``stripe``.
The Stripe SDK is an injectable seam (``stripe_module``) so tests run with a fake — no live
calls. Plan resolution uses ``settings.stripe_plan_to_price`` (internal plan -> Stripe Price),
inverted for webhook price -> plan, so SKUs/pricing can change in Stripe without code edits.
"""

from __future__ import annotations

from typing import Any

import stripe

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

# Stripe subscription-lifecycle event names -> normalized event types.
_EVENT_MAP = {
    "customer.subscription.created": EVENT_SUBSCRIPTION_CREATED,
    "customer.subscription.updated": EVENT_SUBSCRIPTION_UPDATED,
    "customer.subscription.deleted": EVENT_SUBSCRIPTION_DELETED,
}


class StripeAdapter:
    """``PaymentsPort`` implementation for Stripe."""

    name = "stripe"
    signature_header = "stripe-signature"

    def __init__(self, *, stripe_module: Any = None, settings: Settings | None = None) -> None:
        # ``self._stripe`` is the injectable SDK seam (the real ``stripe`` module by default).
        self._stripe: Any = stripe_module if stripe_module is not None else stripe
        self._settings = settings or get_settings()

    # --- plan <-> price mapping ------------------------------------------
    def _plan_to_price(self, plan: str) -> str:
        price_id = self._settings.stripe_plan_to_price.get(plan)
        if not price_id:
            raise PaymentError(f"No Stripe price configured for plan {plan!r}")
        return price_id

    def _price_to_plan(self, price_id: str | None) -> str:
        if not price_id:
            return FREE_PLAN
        for plan, pid in self._settings.stripe_plan_to_price.items():
            if pid == price_id:
                return plan
        return FREE_PLAN

    # --- customer lifecycle ----------------------------------------------
    def _configure(self) -> None:
        self._stripe.api_key = self._settings.stripe_secret_key

    def _ensure_customer(self, account: BillingAccount) -> str:
        existing = account.payments_customer_id
        if existing is not None:
            return existing
        self._configure()
        customer = self._stripe.Customer.create(
            name=account.name, metadata={"organization_id": str(account.id)}
        )
        customer_id: str = customer["id"]
        account.payments_customer_id = customer_id
        return customer_id

    # --- PaymentsPort ----------------------------------------------------
    async def start_checkout(self, account: BillingAccount, plan: str) -> str:
        price_id = self._plan_to_price(plan)
        customer_id = self._ensure_customer(account)
        self._configure()
        session = self._stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=self._settings.payments_success_url,
            cancel_url=self._settings.payments_cancel_url,
        )
        url: str = session["url"]
        return url

    async def open_customer_portal(self, account: BillingAccount) -> str:
        customer_id = self._ensure_customer(account)
        self._configure()
        session = self._stripe.billing_portal.Session.create(
            customer=customer_id, return_url=self._settings.payments_portal_return_url
        )
        url: str = session["url"]
        return url

    def verify_webhook(self, raw_body: bytes, signature: str) -> PaymentEvent:
        secret = self._settings.stripe_webhook_secret or ""
        try:
            event: dict[str, Any] = self._stripe.Webhook.construct_event(
                raw_body, signature, secret
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise WebhookVerificationError(str(exc)) from exc
        return self._to_payment_event(event)

    def _to_payment_event(self, event: dict[str, Any]) -> PaymentEvent:
        obj = event.get("data", {}).get("object", {})
        items = obj.get("items", {}).get("data", [])
        price_id = items[0]["price"]["id"] if items else None
        return PaymentEvent(
            event_id=event["id"],
            event_type=_EVENT_MAP.get(event["type"], EVENT_IGNORED),
            subscription_id=obj.get("id"),
            status=obj.get("status"),
            plan=self._price_to_plan(price_id),
            period_end=to_naive_utc(obj.get("current_period_end")),
            customer_ref=obj.get("customer"),
        )

    async def get_subscription(self, account: BillingAccount) -> SubscriptionState | None:
        if account.payments_customer_id is None:
            return None
        self._configure()
        result = self._stripe.Subscription.list(customer=account.payments_customer_id, limit=1)
        data = result.get("data", [])
        if not data:
            return None
        sub = data[0]
        items = sub.get("items", {}).get("data", [])
        price_id = items[0]["price"]["id"] if items else None
        return SubscriptionState(
            subscription_id=sub["id"],
            status=sub["status"],
            plan=self._price_to_plan(price_id),
            period_end=to_naive_utc(sub.get("current_period_end")),
        )

    async def cancel(self, account: BillingAccount) -> None:
        state = await self.get_subscription(account)
        if state is None:
            return
        self._configure()
        self._stripe.Subscription.cancel(state.subscription_id)
