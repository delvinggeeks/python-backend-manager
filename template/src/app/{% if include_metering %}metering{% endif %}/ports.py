"""The metering + billing seams: ``MeteringPort`` (usage) and ``BillingPort`` (rate/invoice/charge).

Hexagonal ports the router depends on, never a concrete store. The default Postgres-native adapter
is :mod:`app.metering.service`; a managed swap (Lago / OpenMeter / Stripe Meters) implements the
same contract behind ``include_metering``. The session is part of the Postgres-native contract so
ingest can join the request transaction (idempotent + atomic). Requires the `db` extra.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from app.metering.models import Invoice


class WalletError(Exception):
    """A wallet operation cannot proceed (e.g. insufficient balance for a debit)."""


@runtime_checkable
class MeteringPort(Protocol):
    """Records usage events and reads per-meter totals for a period."""

    async def record_usage(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        meter: str,
        quantity: int,
        *,
        idempotency_key: str,
    ) -> bool:
        """Record ``quantity`` of ``meter`` for the org. ``False`` if the key was a duplicate."""
        ...

    async def usage_for_period(
        self, session: AsyncSession, organization_id: uuid.UUID, *, start: datetime, end: datetime
    ) -> dict[str, int]:
        """Sum usage per meter for the org over ``[start, end)``."""
        ...


@runtime_checkable
class BillingPort(Protocol):
    """Rates a period into an ``Invoice`` and charges it (prepaid wallet by default)."""

    async def invoice_period(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        plan: str,
        *,
        start: datetime,
        end: datetime,
    ) -> Invoice:
        """Rate the org's usage over ``[start, end)`` against ``plan`` → a persisted invoice."""
        ...

    async def charge_invoice(self, session: AsyncSession, invoice: Invoice) -> Invoice:
        """Charge an open invoice: atomically debit the org's prepaid wallet (→ ``paid``), or mark
        ``uncollectible`` when the balance is insufficient and there is no external payer."""
        ...
