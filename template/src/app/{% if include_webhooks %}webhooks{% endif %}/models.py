"""The webhook tables — registered delivery targets and the transactional outbox.

``WebhookEndpoint`` is a tenant's outbound target (tenant-scoped; ``secret`` is the per-endpoint
HMAC-SHA256 signing key, stored in the clear because the worker must re-sign each delivery with
it; ``event_types`` is a space-separated subscription list, mirroring how ``app.api_keys`` stores
scopes). ``OutboxEvent`` is the transactional-outbox row: a domain event written in the SAME
transaction as the change that produced it, then drained by the relay. Both map onto the shared
``Base`` from ``app.db.models``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

# Load fastapi_users.db before the adapter's `generics` submodule (import-ordering guard,
# mirrors app.tenancy.models) so the GUID type imports cleanly.
import fastapi_users.db  # noqa: F401  (import-ordering guard)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class WebhookEndpoint(Base):
    """A tenant's outbound webhook target. Deliveries are signed with ``secret``."""

    __tablename__ = "webhook_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(2048))
    secret: Mapped[str] = mapped_column(String(255))
    # Space-separated subscribed event names (e.g. "member.added organization.created").
    event_types: Mapped[str] = mapped_column(String(1024))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class OutboxEvent(Base):
    """A durable domain event awaiting publication — the transactional-outbox row.

    Written (and committed) in the same transaction as the business change that produced it, so the
    event can never be lost to a queue outage between commit and publish. The arq relay
    (:func:`app.webhooks.outbox.drain_outbox`) later reads pending rows, fans each out to the
    subscribed endpoints, and stamps ``published_at``. ``(source, event_id)`` is unique so a
    producer can emit idempotently; ``failed_at`` marks an event dead-lettered after too many
    failed attempts so a poison event can't wedge the relay.
    """

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    # Producing subsystem (e.g. "webhook") — pairs with event_id for idempotent emission.
    source: Mapped[str] = mapped_column(String(64))
    event_id: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(255))
    # Scope tag (the tenant the event belongs to); nullable for system-wide events. Deliberately
    # not a foreign key so the outbox stays generic across producers.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(GUID, default=None)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(String(1024), default=None)
    # NULL until published; the relay claims rows where both timestamps are NULL.
    published_at: Mapped[datetime | None] = mapped_column(default=None, index=True)
    failed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)

    __table_args__ = (UniqueConstraint("source", "event_id", name="uq_outbox_source_event"),)
