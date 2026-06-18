"""Active-provider selection: map ``settings.payments_provider`` -> a ``PaymentsPort`` adapter.

The billing router depends on :func:`get_payments_provider`, so the rest of the app never
names a concrete provider. Adding a provider = implement :class:`~app.billing.ports.PaymentsPort`
in ``app.billing.adapters`` and add ONE entry to ``_PROVIDERS`` below (keep its key in sync
with the ``payments_provider`` Literal in ``Settings`` and the Copier choice). See the
Billing section of the service README.
"""

from __future__ import annotations

from collections.abc import Callable

from app.billing.adapters.razorpay import RazorpayAdapter
from app.billing.adapters.stripe import StripeAdapter
from app.billing.ports import PaymentsPort
from app.core.config import get_settings

# Provider key -> zero-arg factory. Each adapter's __init__ args are all optional (its real
# client + settings are built lazily), so the class itself is a valid factory here.
_PROVIDERS: dict[str, Callable[[], PaymentsPort]] = {
    "stripe": StripeAdapter,
    "razorpay": RazorpayAdapter,
}


def get_payments_provider() -> PaymentsPort:
    """Return the configured payments adapter (used as a FastAPI dependency).

    Selected by ``settings.payments_provider`` (the ``PAYMENTS_PROVIDER`` env var overrides at
    runtime). Raises if an unknown provider is configured, surfacing the misconfiguration
    loudly at request time rather than silently falling back.
    """
    name = get_settings().payments_provider
    try:
        factory = _PROVIDERS[name]
    except KeyError as exc:
        raise RuntimeError(f"Unknown payments_provider: {name!r}") from exc
    return factory()
