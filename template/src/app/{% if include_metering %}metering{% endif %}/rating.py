"""The rating engine: a period's `(plan, usage)` → invoice lines (base + included quota + overage).

Pure and dependency-free — the heart of metering, trivial to unit-test. ``rate`` resolves the plan's
:class:`~app.metering.rate_cards.RateCard`, emits one ``base`` line for the flat fee (if any), then one
``overage`` line per meter whose usage exceeded its included quota (priced per unit). Unknown plans
fall back to ``DEFAULT_PLAN``. The store (:mod:`app.metering.service`) persists these onto an Invoice.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.metering.rate_cards import DEFAULT_PLAN, DEFAULT_RATE_CARDS, RateCard


@dataclass(frozen=True)
class RatedLine:
    """One invoice line — a flat ``base`` charge or a metered ``overage`` charge."""

    kind: str  # "base" | "overage"
    meter: str | None
    quantity: int
    unit_cents: int
    amount_cents: int
    description: str


def rate(
    plan: str,
    usage: dict[str, int],
    *,
    rate_cards: dict[str, RateCard] | None = None,
) -> list[RatedLine]:
    """Rate ``usage`` (per-meter totals) against ``plan``'s rate card → ordered invoice lines.

    The ``base`` line comes first (omitted when the plan is free), then one ``overage`` line per meter
    that exceeded its included quota AND has a non-zero overage price (a zero price = a hard cap, not
    billed). Deterministic: meters are emitted in sorted order.
    """
    cards = rate_cards if rate_cards is not None else DEFAULT_RATE_CARDS
    card = cards.get(plan) or cards.get(DEFAULT_PLAN)
    if card is None:
        return []

    lines: list[RatedLine] = []
    if card.base_cents:
        lines.append(
            RatedLine(
                kind="base",
                meter=None,
                quantity=1,
                unit_cents=card.base_cents,
                amount_cents=card.base_cents,
                description=f"{plan} plan",
            )
        )
    for meter, meter_rate in sorted(card.meters.items()):
        used = usage.get(meter, 0)
        over = max(0, used - meter_rate.included)
        if over and meter_rate.overage_cents:
            amount = over * meter_rate.overage_cents
            lines.append(
                RatedLine(
                    kind="overage",
                    meter=meter,
                    quantity=over,
                    unit_cents=meter_rate.overage_cents,
                    amount_cents=amount,
                    description=f"{meter} overage: {over} × {meter_rate.overage_cents}c",
                )
            )
    return lines


def total_cents(lines: list[RatedLine]) -> int:
    """Sum the line amounts — the invoice total, in minor currency units."""
    return sum(line.amount_cents for line in lines)
