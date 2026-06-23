"""Idempotency keys — replay the cached response for a repeated ``Idempotency-Key`` header.

:class:`~app.idempotency.middleware.IdempotencyMiddleware` intercepts mutating requests that carry
the header and dedupes them through an :class:`~app.idempotency.store.IdempotencyPort` (default:
:class:`~app.idempotency.store.SqlIdempotencyStore`, a Postgres UNIQUE-constraint lock). Wired in
``app.main`` when the capability is on. Requires the `db` extra.
"""

from __future__ import annotations

from app.idempotency.middleware import IdempotencyMiddleware
from app.idempotency.store import IdempotencyPort, SqlIdempotencyStore

__all__ = ["IdempotencyMiddleware", "IdempotencyPort", "SqlIdempotencyStore"]
