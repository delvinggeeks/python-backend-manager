"""Payments adapters — concrete providers behind the :class:`~app.billing.ports.PaymentsPort`.

Each adapter wraps ONE vendor SDK (the vendor edge of the hexagon) and maps its objects onto
the normalized ``PaymentEvent`` / ``SubscriptionState``. Exactly one is active per service,
chosen by ``settings.payments_provider`` via ``app.billing.provider``.
"""

from __future__ import annotations

from app.billing.adapters.razorpay import RazorpayAdapter
from app.billing.adapters.stripe import StripeAdapter

__all__ = ["RazorpayAdapter", "StripeAdapter"]
