"""The transactional-outbox relay — drains ``outbox_events`` and fans each out to its endpoints.

The producer side (:func:`app.webhooks.dispatch.dispatch`) writes an event row in the business
transaction; this module is the consumer the arq worker runs on a schedule
(:func:`app.jobs.tasks.relay_outbox`). :func:`drain_outbox` is deliberately infrastructure-free —
it takes a session and an ``enqueue_fn`` — so the no-Redis test drives it directly with a fake
queue. Delivery is at-least-once (a crash between the enqueue and the ``published_at`` stamp
re-sends), so receivers dedupe on the ``id`` carried in the payload. Requires the `db` + `worker`
extras.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.webhooks.dispatch import WEBHOOK_SOURCE
from app.webhooks.models import OutboxEvent, WebhookEndpoint

log = get_logger(__name__)

# After this many failed publish attempts an event is dead-lettered (``failed_at`` set) so a
# permanently-failing ("poison") event can't wedge the relay; it is kept for inspection, never
# auto-deleted.
DEFAULT_MAX_ATTEMPTS = 5

# The enqueue seam's shape: ``await enqueue_fn(task_name, **kwargs) -> queued?`` (False = the
# backend was unreachable). ``app.jobs.queue.enqueue`` satisfies it; tests pass a fake.
EnqueueFn = Callable[..., Awaitable[bool]]


class OutboxPublishError(Exception):
    """A pending event could not be published this round (e.g. the queue was unreachable)."""


async def drain_outbox(
    session: AsyncSession,
    *,
    enqueue_fn: EnqueueFn,
    limit: int = 100,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> int:
    """Publish pending outbox events, then commit. Returns how many were published this call.

    Idempotent: only unpublished, non-dead-lettered rows are claimed, so re-running never
    double-publishes an event. A publish failure increments ``attempts`` and is retried on the
    next run; once ``attempts`` reaches ``max_attempts`` the event is dead-lettered.
    """
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None), OutboxEvent.failed_at.is_(None))
        .order_by(OutboxEvent.created_at)
        .limit(limit)
    )
    if session.get_bind().dialect.name == "postgresql":
        # Claim rows so concurrent relay runs (multiple workers) never grab the same event;
        # skip_locked lets them make progress on disjoint rows instead of blocking each other.
        stmt = stmt.with_for_update(skip_locked=True)
    events = list((await session.execute(stmt)).scalars().all())

    published = 0
    for event in events:
        try:
            await _fan_out(session, event, enqueue_fn)
        except OutboxPublishError as exc:
            event.attempts += 1
            event.last_error = str(exc)[:1024]
            if event.attempts >= max_attempts:
                event.failed_at = _utcnow()
                log.warning("outbox.dead_letter", event_id=event.event_id, source=event.source)
            else:
                log.info(
                    "outbox.publish_deferred", event_id=event.event_id, attempts=event.attempts
                )
            continue
        event.published_at = _utcnow()
        published += 1
    await session.commit()
    return published


async def _fan_out(session: AsyncSession, event: OutboxEvent, enqueue_fn: EnqueueFn) -> None:
    """Enqueue one signed delivery per active endpoint subscribed to ``event``.

    Raises :class:`OutboxPublishError` on the first rejected enqueue, leaving the whole event
    pending for a later retry. Delivery is therefore at-least-once: if an earlier endpoint was
    already enqueued before a later one was rejected, it is re-enqueued on the retry, so a receiver
    may see a duplicate (it dedupes on the payload ``id``). In practice the queue is shared, so a
    rejection usually means the backend is down and nothing was enqueued this round.
    """
    if event.source != WEBHOOK_SOURCE:
        # No consumer is registered for this source yet — don't wedge the relay; the caller marks
        # it published so it is skipped from now on.
        log.warning("outbox.unknown_source", source=event.source, event_id=event.event_id)
        return
    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.organization_id == event.organization_id,
            WebhookEndpoint.active.is_(True),
        )
    )
    for endpoint in result.scalars().all():
        if event.event_type not in endpoint.event_types.split():
            continue
        queued = await enqueue_fn(
            "deliver_webhook",
            endpoint_id=str(endpoint.id),
            event_type=event.event_type,
            payload=event.payload,
        )
        if not queued:
            raise OutboxPublishError(f"queue unavailable (endpoint {endpoint.id})")


def _utcnow() -> datetime:
    # Naive UTC to match the table's timezone-less DateTime columns (portable across SQLite/PG).
    return datetime.now(UTC).replace(tzinfo=None)
