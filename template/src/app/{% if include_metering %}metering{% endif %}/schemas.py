"""Pydantic request/response schemas for the metering API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UsageRecord(BaseModel):
    """Ingest one usage event. ``idempotency_key`` makes a retried record count once."""

    meter: str = Field(max_length=64)
    quantity: int = Field(ge=0)
    idempotency_key: str = Field(max_length=255)


class UsageSummary(BaseModel):
    """Per-meter usage totals for the current (unbilled) period."""

    period_start: datetime
    period_end: datetime
    usage: dict[str, int]


class WalletTopUp(BaseModel):
    """Add prepaid credits (minor units). ``idempotency_key`` makes a retried top-up apply once."""

    amount_cents: int = Field(gt=0)
    idempotency_key: str = Field(max_length=255)


class WalletRead(BaseModel):
    """A prepaid wallet balance."""

    balance_cents: int
    currency: str


class InvoiceRead(BaseModel):
    """A rated (and possibly charged) invoice."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_start: datetime
    period_end: datetime
    status: str
    currency: str
    total_cents: int
    plan: str
    lines: list[dict[str, Any]]
