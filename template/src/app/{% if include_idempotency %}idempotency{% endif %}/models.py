"""The idempotency-key store — one row per ``(scope, Idempotency-Key)`` on a mutating request.

A client retry that reuses the same key replays the cached response instead of re-running the
handler, so a network retry can't double-charge or double-submit. ``scope`` namespaces the key by
the caller's credential (a hash of the Authorization / API-key header, or the client IP) so one
caller's key can never collide with — or replay — another's. The UNIQUE ``(scope, key)`` IS the
lock: the first request to INSERT it wins and runs the handler; a concurrent duplicate loses the
INSERT and is told to retry. No users/tenancy dependency, so this works in a bare ``db`` service.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, LargeBinary, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class IdempotencyKey(Base):
    """A claimed idempotency key and (once the handler finishes) its cached response."""

    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Per-credential namespace: hash of the Authorization / API-key header, or the client IP.
    scope: Mapped[str] = mapped_column(String(64))
    # Client-supplied key; UNIQUE per scope so the INSERT is the atomic claim (the lock).
    key: Mapped[str] = mapped_column(String(255))
    # Fingerprint of (method, path, body): the same key with a different request → 422 (client bug).
    request_hash: Mapped[str] = mapped_column(String(64))
    # "in_progress" while the handler runs; "completed" once the response is cached.
    status: Mapped[str] = mapped_column(String(20))
    response_status: Mapped[int | None] = mapped_column(Integer, default=None)
    # Cached response headers as ``[[name, value], ...]`` (latin-1), replayed verbatim. Excludes
    # set-cookie + hop-by-hop (no session tokens at rest); see app.idempotency.store.
    response_headers: Mapped[list[list[str]] | None] = mapped_column(JSON, default=None)
    response_body: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Past this the key is treated as absent (reclaimable) — bounds the crash window + storage.
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    __table_args__ = (UniqueConstraint("scope", "key", name="uq_idempotency_keys_scope_key"),)
