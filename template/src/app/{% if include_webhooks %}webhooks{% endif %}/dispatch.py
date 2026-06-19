"""Fan-out of a domain event to a tenant's subscribed webhook endpoints.

:func:`dispatch` enqueues ONE delivery task per active endpoint subscribed to the event — the
HTTP POST happens later in the worker (:func:`app.jobs.tasks.deliver_webhook`), never inline,
so a slow or unreachable receiver can't delay the request that triggered the event. Enqueue is
best-effort (:func:`app.jobs.queue.enqueue` swallows a dead queue), so dispatch never raises
into the caller. Returns the number of deliveries enqueued.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.queue import enqueue
from app.webhooks.models import WebhookEndpoint


async def dispatch(
    session: AsyncSession,
    *,
    event_type: str,
    organization_id: uuid.UUID,
    data: dict[str, Any],
) -> int:
    """Enqueue a signed delivery for each active endpoint subscribed to ``event_type``."""
    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.organization_id == organization_id,
            WebhookEndpoint.active.is_(True),
        )
    )
    payload = {
        "event_type": event_type,
        "organization_id": str(organization_id),
        "data": data,
    }
    enqueued = 0
    for endpoint in result.scalars().all():
        if event_type not in endpoint.event_types.split():
            continue
        # Best-effort: a dead queue returns False here, never an exception.
        if await enqueue(
            "deliver_webhook",
            endpoint_id=str(endpoint.id),
            event_type=event_type,
            payload=payload,
        ):
            enqueued += 1
    return enqueued
