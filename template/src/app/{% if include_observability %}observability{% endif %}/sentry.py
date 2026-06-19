"""Optional Sentry error reporting — a no-op unless SENTRY_DSN is configured.

Same suppress-when-unconfigured contract as the email / jobs capabilities: importing this is
always safe, and ``init_sentry`` does nothing when no DSN is set, so a fresh service never
reports anywhere by accident. When a DSN is present, Sentry's FastAPI integration captures
unhandled exceptions (with the active OpenTelemetry trace attached).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app import __version__
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Settings

log = get_logger(__name__)


def init_sentry(settings: Settings) -> bool:
    """Initialise Sentry when SENTRY_DSN is set. Returns True when enabled, False otherwise."""
    if not settings.sentry_dsn:
        return False

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        release=__version__,
    )
    log.info("observability.sentry_enabled", environment=settings.environment)
    return True
