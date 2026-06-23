"""Default per-plan rate cards — the metered prices. Pure data, dependency-free, easy to override.

A **rate card** is a plan's base price plus, per metered dimension, an **included quota** and a
**per-unit overage** price. The rating engine (:mod:`app.metering.rating`) maps a `(plan, usage)`
pair onto invoice lines using these. Plan keys mirror ``app.billing.entitlements`` (free / pro /
enterprise) when billing is present; a metering-only service rates every org against ``DEFAULT_PLAN``.
Replace these with your real prices — they are intentionally plain data so they unit-test trivially.
"""

from __future__ import annotations

from dataclasses import dataclass

# Currency for the default cards (ISO-4217, lower-case). Amounts are in MINOR units (e.g. cents).
DEFAULT_CURRENCY = "usd"
# The plan a metering-only service (no billing module) rates every org against.
DEFAULT_PLAN = "free"


@dataclass(frozen=True)
class MeterRate:
    """The price of one metered dimension on a plan: an included quota, then per-unit overage."""

    included: int  # units bundled into the plan's base price (no overage below this)
    overage_cents: int  # price per unit beyond ``included``, in minor currency units (0 = hard cap)


@dataclass(frozen=True)
class RateCard:
    """A plan's flat base price plus its per-meter rates."""

    base_cents: int
    currency: str
    meters: dict[str, MeterRate]


# Default rate cards keyed by internal plan key. Example dimensions: API calls + LLM tokens (the
# AI-usage billable unit). ``overage_cents=0`` means the included quota is a hard cap, not billed.
DEFAULT_RATE_CARDS: dict[str, RateCard] = {
    "free": RateCard(
        base_cents=0,
        currency=DEFAULT_CURRENCY,
        meters={"api_calls": MeterRate(included=1_000, overage_cents=0)},
    ),
    "pro": RateCard(
        base_cents=4_900,
        currency=DEFAULT_CURRENCY,
        meters={
            "api_calls": MeterRate(included=100_000, overage_cents=1),
            "tokens": MeterRate(included=1_000_000, overage_cents=0),
        },
    ),
    "enterprise": RateCard(
        base_cents=49_900,
        currency=DEFAULT_CURRENCY,
        meters={
            "api_calls": MeterRate(included=1_000_000, overage_cents=1),
            "tokens": MeterRate(included=10_000_000, overage_cents=0),
        },
    ),
}
