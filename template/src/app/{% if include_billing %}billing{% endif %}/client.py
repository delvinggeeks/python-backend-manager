"""Thin wrapper around the Stripe SDK — the single seam mocked in tests.

Every function reads credentials from settings at call time (test-mode keys via env, never
hard-coded) and returns plain dicts, so routes never touch the ``stripe`` module directly
and tests can monkeypatch these functions with no live network calls.
"""

from __future__ import annotations

from typing import Any

import stripe

from app.core.config import get_settings


class WebhookVerificationError(Exception):
    """Raised when a Stripe webhook signature fails verification."""


def _configure() -> None:
    """Point the Stripe SDK at the configured secret key (read fresh each call)."""
    stripe.api_key = get_settings().stripe_secret_key


def create_customer(*, name: str, organization_id: str) -> str:
    """Create a Stripe customer for an org and return its id."""
    _configure()
    customer = stripe.Customer.create(name=name, metadata={"organization_id": organization_id})
    customer_id: str = customer["id"]
    return customer_id


def create_checkout_session(*, customer_id: str, price_id: str) -> dict[str, str]:
    """Create a subscription Checkout Session; return its id + redirect url."""
    _configure()
    settings = get_settings()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
    )
    return {"id": session["id"], "url": session["url"]}


def create_billing_portal_session(*, customer_id: str) -> dict[str, str]:
    """Create a customer-portal session; return its redirect url."""
    _configure()
    session = stripe.billing_portal.Session.create(
        customer=customer_id, return_url=get_settings().stripe_portal_return_url
    )
    return {"url": session["url"]}


def construct_event(payload: bytes, signature: str) -> dict[str, Any]:
    """Verify a webhook signature and return the parsed event, else raise.

    Raises ``WebhookVerificationError`` on a bad/forged signature or malformed payload — the
    webhook route turns that into a ``400``.
    """
    secret = get_settings().stripe_webhook_secret or ""
    try:
        event: dict[str, Any] = stripe.Webhook.construct_event(payload, signature, secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise WebhookVerificationError(str(exc)) from exc
    return event
