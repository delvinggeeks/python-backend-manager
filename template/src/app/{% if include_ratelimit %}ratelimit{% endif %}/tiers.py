"""Per-plan rate tiers + the auth tier. Pure data + settings lookups, so it is trivial to unit-test.

A ``RateTier`` is ``limit`` requests per ``window_seconds``. ``PLAN_TIERS`` is keyed by the INTERNAL
plan key — the same keys ``app.billing.entitlements`` uses (free / pro / enterprise) — so a service
with billing on maps its org's subscription straight onto a request budget. An anonymous, no-plan or
unknown-plan caller gets :func:`default_tier`. Edit ``PLAN_TIERS`` to match your real packaging.

The default and auth tiers come from settings so they can be tuned per environment without a code
change; the per-plan budgets stay in code because they are product packaging, not configuration.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class RateTier:
    """A limit: ``limit`` requests per ``window_seconds``."""

    limit: int
    window_seconds: int


# Per-plan request budgets, keyed by the internal plan key. Rate limiting protects the platform; it
# is NOT the quota/metering system — durable per-org usage accounting and billing live in P7's
# `app.metering`, so these are protection ceilings, not entitlements to sell against.
PLAN_TIERS: dict[str, RateTier] = {
    "free": RateTier(limit=60, window_seconds=60),
    "pro": RateTier(limit=600, window_seconds=60),
    "enterprise": RateTier(limit=6_000, window_seconds=60),
}


def default_tier() -> RateTier:
    """The tier for anonymous / no-plan / unknown-plan traffic (from settings)."""
    settings = get_settings()
    return RateTier(
        limit=settings.ratelimit_default_limit,
        window_seconds=settings.ratelimit_default_window_seconds,
    )


def auth_tier() -> RateTier:
    """The tighter tier for login / refresh — credential-stuffing defense (from settings)."""
    settings = get_settings()
    return RateTier(
        limit=settings.ratelimit_auth_limit,
        window_seconds=settings.ratelimit_auth_window_seconds,
    )


def tier_for_plan(plan: str | None) -> RateTier:
    """The rate tier for ``plan``, falling back to :func:`default_tier` for unknown/absent plans."""
    if plan is None:
        return default_tier()
    return PLAN_TIERS.get(plan, default_tier())
