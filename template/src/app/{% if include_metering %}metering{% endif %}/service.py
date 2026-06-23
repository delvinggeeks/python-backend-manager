"""Postgres-native MeteringPort + BillingPort — the default metering engine.

``record_usage`` is idempotent (UNIQUE ``(org, idempotency_key)``); ``usage_for_period`` aggregates;
``invoice_period`` rates the period via :mod:`app.metering.rating` and persists an ``open`` ``Invoice``;
``charge_invoice`` debits the prepaid wallet **atomically** (a conditional ``UPDATE ... WHERE balance >=
amount`` — the same race-free pattern as the auth refresh rotation), marking the invoice ``paid`` or
``uncollectible``. ``top_up`` credits the wallet idempotently. Requires the `db` extra.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.metering.models import CustomerWallet, Invoice, UsageEvent, WalletTransaction
from app.metering.rate_cards import DEFAULT_CURRENCY
from app.metering.rating import RatedLine, rate, total_cents

log = get_logger(__name__)

_OPEN = "open"
_PAID = "paid"
_UNCOLLECTIBLE = "uncollectible"


class SqlMeteringService:
    """The default Postgres-native adapter implementing both MeteringPort and BillingPort."""

    async def record_usage(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        meter: str,
        quantity: int,
        *,
        idempotency_key: str,
    ) -> bool:
        """Append a usage event; returns ``False`` if ``idempotency_key`` was already recorded."""
        session.add(
            UsageEvent(
                organization_id=organization_id,
                meter=meter,
                quantity=quantity,
                idempotency_key=idempotency_key,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False
        return True

    async def usage_for_period(
        self, session: AsyncSession, organization_id: uuid.UUID, *, start: datetime, end: datetime
    ) -> dict[str, int]:
        """Sum usage per meter for the org over ``[start, end)``."""
        result = await session.execute(
            select(UsageEvent.meter, func.sum(UsageEvent.quantity))
            .where(
                UsageEvent.organization_id == organization_id,
                UsageEvent.created_at >= start,
                UsageEvent.created_at < end,
            )
            .group_by(UsageEvent.meter)
        )
        return {meter: int(total) for meter, total in result.all()}

    async def invoice_period(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        plan: str,
        *,
        start: datetime,
        end: datetime,
    ) -> Invoice:
        """Rate the org's usage over ``[start, end)`` against ``plan`` → a persisted ``open`` invoice."""
        usage = await self.usage_for_period(session, organization_id, start=start, end=end)
        lines = rate(plan, usage)
        invoice = Invoice(
            organization_id=organization_id,
            period_start=start,
            period_end=end,
            status=_OPEN,
            currency=DEFAULT_CURRENCY,
            total_cents=total_cents(lines),
            plan=plan,
            lines=[_line_dict(line) for line in lines],
        )
        session.add(invoice)
        await session.commit()
        await session.refresh(invoice)
        return invoice

    async def charge_invoice(self, session: AsyncSession, invoice: Invoice) -> Invoice:
        """Charge an ``open`` invoice by atomically debiting the prepaid wallet (idempotent)."""
        if invoice.status != _OPEN:
            return invoice  # already charged — idempotent
        if invoice.total_cents == 0:
            invoice.status = _PAID
            invoice.charged_at = _utcnow()
            await session.commit()
            return invoice
        # Atomic debit: only succeeds if the balance covers it (no check-then-set race).
        result = await session.execute(
            update(CustomerWallet)
            .where(
                CustomerWallet.organization_id == invoice.organization_id,
                CustomerWallet.balance_cents >= invoice.total_cents,
            )
            .values(balance_cents=CustomerWallet.balance_cents - invoice.total_cents)
            .returning(CustomerWallet.id)
        )
        wallet_id = result.scalar_one_or_none()
        if wallet_id is None:
            invoice.status = _UNCOLLECTIBLE
            log.warning("metering.charge_uncollectible", invoice_id=str(invoice.id))
        else:
            invoice.status = _PAID
            invoice.charged_at = _utcnow()
            session.add(
                WalletTransaction(
                    wallet_id=wallet_id,
                    delta_cents=-invoice.total_cents,
                    reason="invoice",
                    idempotency_key=f"invoice:{invoice.id}",
                    invoice_id=invoice.id,
                )
            )
        await session.commit()
        return invoice

    async def top_up(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        amount_cents: int,
        *,
        idempotency_key: str,
        currency: str = DEFAULT_CURRENCY,
    ) -> CustomerWallet:
        """Credit the org's wallet (creating it on first use); idempotent per ``idempotency_key``."""
        wallet = await self._get_or_create_wallet(session, organization_id, currency)
        session.add(
            WalletTransaction(
                wallet_id=wallet.id,
                delta_cents=amount_cents,
                reason="topup",
                idempotency_key=idempotency_key,
            )
        )
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()  # key already applied — no-op
            return await self._get_or_create_wallet(session, organization_id, currency)
        await session.execute(
            update(CustomerWallet)
            .where(CustomerWallet.id == wallet.id)
            .values(balance_cents=CustomerWallet.balance_cents + amount_cents)
        )
        await session.commit()
        await session.refresh(wallet)
        return wallet

    async def get_wallet(
        self, session: AsyncSession, organization_id: uuid.UUID
    ) -> CustomerWallet | None:
        """Return the org's wallet, or ``None`` if it has never been topped up."""
        return (
            await session.execute(
                select(CustomerWallet).where(CustomerWallet.organization_id == organization_id)
            )
        ).scalar_one_or_none()

    async def _get_or_create_wallet(
        self, session: AsyncSession, organization_id: uuid.UUID, currency: str
    ) -> CustomerWallet:
        wallet = await self.get_wallet(session, organization_id)
        if wallet is None:
            wallet = CustomerWallet(
                organization_id=organization_id, balance_cents=0, currency=currency
            )
            session.add(wallet)
            await session.flush()
        return wallet


def _line_dict(line: RatedLine) -> dict[str, object]:
    return {
        "kind": line.kind,
        "meter": line.meter,
        "quantity": line.quantity,
        "unit_cents": line.unit_cents,
        "amount_cents": line.amount_cents,
        "description": line.description,
    }


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
