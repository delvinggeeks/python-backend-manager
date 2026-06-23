"""The idempotency store — the seam behind which a key is claimed, completed, replayed, or purged.

:class:`IdempotencyPort` is the swap contract (a Redis adapter is possible later for high-volume
non-financial endpoints); :class:`SqlIdempotencyStore` is the default Postgres adapter. Atomicity
comes from the UNIQUE ``(scope, key)`` constraint: :meth:`claim` first tries to INSERT an
``in_progress`` row. If the INSERT wins, the request OWNS the key and runs the handler; if it loses
(``IntegrityError``) the existing row is inspected, which serializes concurrent duplicates without
an explicit lock. An expired row is reclaimed (treated as absent). Requires the `db` extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol, runtime_checkable

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.core.logging import get_logger
from app.db.session import SessionFactory
from app.idempotency.models import IdempotencyKey

log = get_logger(__name__)

_IN_PROGRESS = "in_progress"
_COMPLETED = "completed"

# Not cached/replayed: set-cookie (no session tokens at rest) + hop-by-hop headers (connection-
# specific, must not be forwarded). Everything else (Location, ETag, Content-*, ...) is replayed.
_EXCLUDED_HEADERS = frozenset(
    {
        b"set-cookie",
        b"connection",
        b"keep-alive",
        b"transfer-encoding",
        b"upgrade",
        b"te",
        b"trailers",
        b"proxy-authenticate",
        b"proxy-authorization",
    }
)


@dataclass(frozen=True)
class CachedResponse:
    """A completed handler's response, replayed verbatim to a duplicate request."""

    status: int
    headers: list[tuple[bytes, bytes]]
    body: bytes


@dataclass(frozen=True)
class ClaimResult:
    """The outcome of claiming a key.

    ``owned`` → this request runs the handler; ``replay`` → return ``cached`` (handler already ran);
    ``in_progress`` → a concurrent request holds the key (the caller returns 409); ``mismatch`` →
    the key was reused with a different request body (the caller returns 422).
    """

    outcome: Literal["owned", "replay", "in_progress", "mismatch"]
    cached: CachedResponse | None = None


@runtime_checkable
class IdempotencyPort(Protocol):
    """The store contract the middleware speaks (swap the adapter, keep the middleware)."""

    async def claim(
        self, key: str, *, scope: str, request_hash: str, ttl_seconds: int
    ) -> ClaimResult:
        """Atomically claim ``key`` within ``scope`` for this request, or report prior use."""
        ...

    async def complete(
        self,
        key: str,
        *,
        scope: str,
        status: int,
        headers: list[tuple[bytes, bytes]],
        body: bytes,
    ) -> None:
        """Cache the handler's response against ``(scope, key)`` so a retry can replay it."""
        ...

    async def release(self, key: str, *, scope: str) -> None:
        """Drop an unfinished (``in_progress``) claim so the request can be retried fresh."""
        ...

    async def purge_expired(self) -> int:
        """Delete expired rows (storage reclaim); returns how many were removed."""
        ...


class SqlIdempotencyStore:
    """Postgres/SQLite-backed :class:`IdempotencyPort` (the UNIQUE constraint is the lock)."""

    async def claim(
        self, key: str, *, scope: str, request_hash: str, ttl_seconds: int
    ) -> ClaimResult:
        """See :meth:`IdempotencyPort.claim`. Fast path is a single INSERT."""
        now = _utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds)
        async with SessionFactory() as session:
            session.add(
                IdempotencyKey(
                    scope=scope,
                    key=key,
                    request_hash=request_hash,
                    status=_IN_PROGRESS,
                    expires_at=expires_at,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
            else:
                return ClaimResult("owned")

        # The INSERT lost the race: inspect (and possibly reclaim) the existing row.
        async with SessionFactory() as session:
            stmt = select(IdempotencyKey).where(
                IdempotencyKey.scope == scope, IdempotencyKey.key == key
            )
            if session.get_bind().dialect.name == "postgresql":
                stmt = stmt.with_for_update()
            record = (await session.execute(stmt)).scalar_one_or_none()
            if record is None:
                # The winner rolled back between our failed INSERT and this SELECT; tell the caller
                # it's in progress so it retries rather than racing a second INSERT here.
                return ClaimResult("in_progress")
            if record.expires_at <= now:
                record.request_hash = request_hash
                record.status = _IN_PROGRESS
                record.response_status = None
                record.response_headers = None
                record.response_body = None
                record.expires_at = expires_at
                await session.commit()
                return ClaimResult("owned")
            if record.request_hash != request_hash:
                return ClaimResult("mismatch")
            if record.status == _COMPLETED:
                headers = [
                    (name.encode("latin-1"), value.encode("latin-1"))
                    for name, value in (record.response_headers or [])
                ]
                return ClaimResult(
                    "replay",
                    CachedResponse(
                        status=record.response_status
                        if record.response_status is not None
                        else 200,
                        headers=headers,
                        body=record.response_body or b"",
                    ),
                )
            return ClaimResult("in_progress")

    async def complete(
        self,
        key: str,
        *,
        scope: str,
        status: int,
        headers: list[tuple[bytes, bytes]],
        body: bytes,
    ) -> None:
        """See :meth:`IdempotencyPort.complete`."""
        stored = [
            [name.decode("latin-1"), value.decode("latin-1")]
            for name, value in headers
            if name.lower() not in _EXCLUDED_HEADERS
        ]
        async with SessionFactory() as session:
            record = (
                await session.execute(
                    select(IdempotencyKey).where(
                        IdempotencyKey.scope == scope, IdempotencyKey.key == key
                    )
                )
            ).scalar_one_or_none()
            if record is None:
                return
            record.status = _COMPLETED
            record.response_status = status
            record.response_headers = stored
            record.response_body = body
            await session.commit()

    async def release(self, key: str, *, scope: str) -> None:
        """See :meth:`IdempotencyPort.release`."""
        async with SessionFactory() as session:
            record = (
                await session.execute(
                    select(IdempotencyKey).where(
                        IdempotencyKey.scope == scope, IdempotencyKey.key == key
                    )
                )
            ).scalar_one_or_none()
            if record is not None and record.status == _IN_PROGRESS:
                await session.delete(record)
                await session.commit()

    async def purge_expired(self) -> int:
        """See :meth:`IdempotencyPort.purge_expired`."""
        async with SessionFactory() as session:
            result = await session.execute(
                delete(IdempotencyKey)
                .where(IdempotencyKey.expires_at <= _utcnow())
                .returning(IdempotencyKey.id)
            )
            deleted = len(list(result.scalars().all()))
            await session.commit()
            if deleted:
                log.info("idempotency.purged", count=deleted)
            return deleted


def _utcnow() -> datetime:
    # Naive UTC to match the table's timezone-less DateTime columns (portable across SQLite/PG).
    return datetime.now(UTC).replace(tzinfo=None)
