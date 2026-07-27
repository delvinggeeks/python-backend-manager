"""Postgres-native MeteringPort + BillingPort — the default metering engine.

``record_usage`` is idempotent (UNIQUE ``(org, key)``); ``usage_for_period`` aggregates;
``invoice_period`` rates the period via :mod:`app.metering.rating` and persists an ``open`` invoice;
``charge_invoice`` debits the prepaid wallet **atomically** (a conditional ``UPDATE ... WHERE
balance >= amount`` — the race-free pattern from the auth refresh rotation), marking the invoice
``paid`` or ``uncollectible``. ``top_up`` credits the wallet idempotently. Requires the `db` extra.
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
            # Only a duplicate (org, key) is a benign no-op; re-raise anything else (e.g. a bad
            # org FK) rather than silently dropping a billable event.
            duplicate = await session.execute(
                select(UsageEvent.id).where(
                    UsageEvent.organization_id == organization_id,
                    UsageEvent.idempotency_key == idempotency_key,
                )
            )
            if duplicate.scalar_one_or_none() is not None:
                return False
            raise
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
        """Rate the org's usage over ``[start, end)`` against ``plan`` → a persisted invoice."""
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
        try:
            await session.commit()
        except IntegrityError:
            # UNIQUE (org, period_start): this period already has an invoice (a concurrent or
            # retried close) — converge on the existing one rather than double-invoicing the period.
            await session.rollback()
            existing = (
                await session.execute(
                    select(Invoice).where(
                        Invoice.organization_id == organization_id, Invoice.period_start == start
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            raise
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
            await session.commit()
            return invoice
        invoice.status = _PAID
        invoice.charged_at = _utcnow()
        # The invoice-scoped key is the exactly-once guard: it MUST stay derived from invoice.id, so
        # a concurrent/retried charge collides here and its debit is rolled back below (debit-once).
        session.add(
            WalletTransaction(
                wallet_id=wallet_id,
                organization_id=invoice.organization_id,
                delta_cents=-invoice.total_cents,
                reason="invoice",
                idempotency_key=f"invoice:{invoice.id}",
                invoice_id=invoice.id,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            # A concurrent charge already debited for this invoice. Our debit + status flip are
            # rolled back here (so the wallet is debited exactly once); return the already-charged
            # invoice rather than surfacing a 500 — the charge is idempotent.
            await session.rollback()
            reloaded = await session.get(Invoice, invoice.id)
            return reloaded if reloaded is not None else invoice
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
        """Credit the org's wallet (creating it on first use); idempotent per ``key``."""
        wallet = await self._get_or_create_wallet(session, organization_id, currency)
        session.add(
            WalletTransaction(
                wallet_id=wallet.id,
                organization_id=organization_id,
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
            try:
                await session.flush()
            except IntegrityError:
                # A concurrent request created the wallet first (UNIQUE organization_id) — reuse it.
                await session.rollback()
                existing = await self.get_wallet(session, organization_id)
                if existing is not None:
                    return existing
                raise
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
