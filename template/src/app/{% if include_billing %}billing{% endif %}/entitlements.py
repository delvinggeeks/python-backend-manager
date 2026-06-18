"""Plan -> feature entitlements. Pure and dependency-free, so it is trivial to unit-test.

A subscription's ``plan`` (resolved from its Stripe Price via ``settings.stripe_price_to_plan``)
maps here to a frozenset of feature flags. ``require_feature(...)`` in
``app.billing.dependencies`` turns these into route guards. An org with no *active*
subscription falls back to ``FREE_PLAN``'s entitlements.
"""

from __future__ import annotations

# Internal plan keys. Stripe Price ids are mapped onto these via
# ``settings.stripe_price_to_plan``, so SKUs/pricing can change in Stripe without touching
# the entitlements logic.
FREE_PLAN = "free"
PRO_PLAN = "pro"
ENTERPRISE_PLAN = "enterprise"

# Subscription statuses that grant the paid plan's features. Anything else (``past_due``,
# ``canceled``, ``unpaid``, ``incomplete``, ...) falls back to the free tier.
ACTIVE_STATUSES = frozenset({"active", "trialing"})

FEATURES_BY_PLAN: dict[str, frozenset[str]] = {
    FREE_PLAN: frozenset({"core"}),
    PRO_PLAN: frozenset({"core", "advanced_analytics"}),
    ENTERPRISE_PLAN: frozenset(
        {"core", "advanced_analytics", "priority_support", "sso"}
    ),
}


def features_for_plan(plan: str | None) -> frozenset[str]:
    """Return the feature set granted by ``plan``, defaulting to the free tier."""
    return FEATURES_BY_PLAN.get(plan or FREE_PLAN, FEATURES_BY_PLAN[FREE_PLAN])


def plan_has_feature(plan: str | None, feature: str) -> bool:
    """True iff ``plan`` grants ``feature``."""
    return feature in features_for_plan(plan)


def _ci_gate_proof_deliberate_type_error() -> int:
    # DELIBERATE mypy error to prove the capability gate blocks auto-merge. This file is
    # gated behind include_billing, so ONLY the billing capability leg should go red.
    return "not an int"
