"""Plan -> feature entitlements. Pure and dependency-free, so it is trivial to unit-test.

A subscription's ``plan`` (an INTERNAL plan key the active provider's adapter resolves from
its own price/plan id) maps here to a frozenset of feature flags. ``require_feature(...)`` in
``app.billing.dependencies`` turns these into route guards. An org with no *active*
subscription falls back to ``FREE_PLAN``'s entitlements. This layer is provider-agnostic — it
never sees a Stripe/Razorpay id.
"""

from __future__ import annotations

# Internal plan keys. Each provider's adapter maps its own price/plan ids onto these (via
# ``settings.stripe_plan_to_price`` / ``settings.razorpay_plan_to_plan_id``), so SKUs/pricing
# can change with the provider without touching the entitlements logic.
FREE_PLAN = "free"
PRO_PLAN = "pro"
ENTERPRISE_PLAN = "enterprise"

# Subscription statuses that grant the paid plan's features. Anything else (``past_due``,
# ``canceled``, ``unpaid``, ``incomplete``, ...) falls back to the free tier.
ACTIVE_STATUSES = frozenset({"active", "trialing"})

FEATURES_BY_PLAN: dict[str, frozenset[str]] = {
    FREE_PLAN: frozenset({"core"}),
    PRO_PLAN: frozenset({"core", "advanced_analytics"}),
    ENTERPRISE_PLAN: frozenset({"core", "advanced_analytics", "priority_support", "sso"}),
}


def features_for_plan(plan: str | None) -> frozenset[str]:
    """Return the feature set granted by ``plan``, defaulting to the free tier."""
    return FEATURES_BY_PLAN.get(plan or FREE_PLAN, FEATURES_BY_PLAN[FREE_PLAN])


def plan_has_feature(plan: str | None, feature: str) -> bool:
    """True iff ``plan`` grants ``feature``."""
    return feature in features_for_plan(plan)
