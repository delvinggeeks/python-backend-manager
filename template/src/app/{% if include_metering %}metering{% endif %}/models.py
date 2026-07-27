"""Metering & billing tables: usage events, invoices, and a prepaid wallet. Requires `db` + `users`.

``UsageEvent`` is the append-only meter ledger — idempotent per ``(organization_id, key)`` so a
retried ingest counts once. ``Invoice`` is a rated period (line items as JSON, from the rating
engine). ``CustomerWallet`` + ``WalletTransaction`` are the prepaid credit balance and its atomic
debit/top-up ledger. All org-scoped (FK ``organizations.id``) and mapped onto the shared ``Base``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

# Same import-ordering guard as app.tenancy/billing models: load fastapi_users.db before the
# adapter's `generics` submodule so the re-exported GUID type imports cleanly.
import fastapi_users.db  # noqa: F401  (import-ordering guard)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class UsageEvent(Base):
    """One recorded unit of metered usage. Idempotent per ``(organization_id, idempotency_key)``."""

    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    meter: Mapped[str] = mapped_column(String(64), index=True)
    quantity: Mapped[int] = mapped_column(BigInteger)
    # Client-supplied dedupe key; UNIQUE per org so a retried ingest is counted exactly once.
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_usage_org_idem"),
    )


class Invoice(Base):
    """A rated billing period for an org — the line items are the rating engine's output as JSON."""

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    # "draft" → "open" (issued) → "paid" (charged) | "uncollectible" (charge failed, no wallet).
    status: Mapped[str] = mapped_column(String(20), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    total_cents: Mapped[int] = mapped_column(BigInteger)
    plan: Mapped[str] = mapped_column(String(50))
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    charged_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    # One invoice per (org, period): a concurrent / retried close converges, never double-bills.
    __table_args__ = (
        UniqueConstraint("organization_id", "period_start", name="uq_invoice_org_period"),
    )


class CustomerWallet(Base):
    """An org's prepaid credit balance (minor units). One per org; debited atomically on charge."""

    __tablename__ = "customer_wallets"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, index=True
    )
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class WalletTransaction(Base):
    """An append-only wallet ledger entry — a positive top-up or a negative debit."""

    __tablename__ = "wallet_transactions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("customer_wallets.id", ondelete="CASCADE"), index=True
    )
    # Denormalised from the parent wallet so this row can be RLS-protected on a LOCAL fact.
    # The alternative — a policy doing EXISTS against customer_wallets — makes every read of the
    # highest-write table in the schema carry a per-row subquery, and gives the schema a second
    # policy shape that every future auditor has to learn. One shape everywhere, checked locally.
    # Kept in step with the wallet by the service layer, which writes both inside one transaction.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    delta_cents: Mapped[int] = mapped_column(BigInteger)  # positive top-up, negative debit
    reason: Mapped[str] = mapped_column(String(64))
    # UNIQUE (index) so a retried top-up / debit applies once (idempotent wallet mutation).
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(GUID, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
