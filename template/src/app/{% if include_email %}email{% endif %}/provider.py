"""Active-provider selection: map ``settings.email_provider`` -> an ``EmailPort`` adapter.

Callers (the user-manager hooks, any notification code) depend on :func:`get_email_provider`, so
the rest of the app never names a concrete provider. Adding a provider = implement
:class:`~app.email.ports.EmailPort` in ``app.email.adapters`` and add ONE entry to ``_PROVIDERS``
below (keep its key in sync with the ``email_provider`` Literal in ``Settings`` and the Copier
choice). See the Email section of the service README.
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.config import get_settings
from app.email.adapters.console import ConsoleEmailAdapter
from app.email.adapters.ses import SESAdapter
from app.email.adapters.smtp import SMTPAdapter
from app.email.ports import EmailPort

# Provider key -> zero-arg factory. Each adapter's __init__ args are all optional (its real
# transport + settings are built lazily), so the class itself is a valid factory here.
_PROVIDERS: dict[str, Callable[[], EmailPort]] = {
    "smtp": SMTPAdapter,
    "ses": SESAdapter,
    "console": ConsoleEmailAdapter,
}


def get_email_provider() -> EmailPort:
    """Return the configured email adapter (used by the send helpers / user-manager hooks).

    Selected by ``settings.email_provider`` (``EMAIL_PROVIDER`` overrides at runtime). When
    ``settings.email_suppress_send`` is set, the console backend is returned so nothing sends —
    the explicit dev/test kill-switch. An unknown provider raises, surfacing the misconfig loudly.
    """
    settings = get_settings()
    if settings.email_suppress_send:
        return ConsoleEmailAdapter()
    name = settings.email_provider
    try:
        factory = _PROVIDERS[name]
    except KeyError as exc:
        raise RuntimeError(f"Unknown email_provider: {name!r}") from exc
    return factory()
