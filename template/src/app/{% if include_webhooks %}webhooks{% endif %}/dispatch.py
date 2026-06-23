"""Record a domain event for durable, asynchronous fan-out to a tenant's webhook endpoints.

:func:`dispatch` writes ONE row into the transactional outbox (``outbox_events``) inside the
caller's transaction — so the event commits atomically with the change that produced it and can
never be lost to a queue outage. The arq relay (:func:`app.webhooks.outbox.drain_outbox`) later
reads the row and enqueues one signed delivery per subscribed endpoint. This replaces the former
commit-then-enqueue dual write, which silently dropped events whenever Redis was unreachable in
the window between the database commit and the enqueue.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.webhooks.models import OutboxEvent

# The outbox ``source`` tag for webhook events (pairs with event_id for idempotent emission).
WEBHOOK_SOURCE = "webhook"


async def dispatch(
    session: AsyncSession,
    *,
    event_type: str,
    organization_id: uuid.UUID,
    data: dict[str, Any],
    event_id: str | None = None,
) -> OutboxEvent:
    """Append an ``event_type`` event to the outbox for the relay to deliver.

    The row is added and flushed into ``session`` but NOT committed — it joins the caller's
    transaction, so it lands atomically with the business change. Pass ``event_id`` to emit
    idempotently: a duplicate ``(source, event_id)`` violates the table's unique constraint.
    Returns the created :class:`~app.webhooks.models.OutboxEvent`.
    """
    eid = event_id or str(uuid.uuid4())
    event = OutboxEvent(
        source=WEBHOOK_SOURCE,
        event_id=eid,
        event_type=event_type,
        organization_id=organization_id,
        payload={
            "id": eid,
            "event_type": event_type,
            "organization_id": str(organization_id),
            "data": data,
        },
    )
    session.add(event)
    await session.flush()
    return event
