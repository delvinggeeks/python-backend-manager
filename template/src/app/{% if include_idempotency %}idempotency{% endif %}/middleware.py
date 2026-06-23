"""Stripe-style idempotency for mutating requests — a pure-ASGI middleware.

When a ``POST``/``PUT``/``PATCH``/``DELETE`` carries an ``Idempotency-Key`` header, the middleware
buffers the request body, derives a per-credential ``scope`` (so one caller's key can't collide
with another's), fingerprints ``(method, path, body)``, and asks the store to claim it:

- ``owned`` → it replays the buffered body to the app, captures the response (status < 500 is final
  and cached; a 5xx or an over-large body releases the claim), and streams it back.
- ``replay`` → it returns the cached response (status + headers + body) **without running the
  handler** (so no second side effect), tagged ``Idempotent-Replayed: true``.
- ``in_progress`` → ``409`` (a concurrent request holds the key); ``mismatch`` → ``422`` (the key
  was reused with a different request body).

A request whose body exceeds the size cap is passed straight through (never buffered whole). Any
request without the header — and every non-mutating request — passes straight through untouched,
so the middleware is safe to leave installed. Requires the `db` extra.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import get_logger
from app.idempotency.store import IdempotencyPort

log = get_logger(__name__)

_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_HEADER = b"idempotency-key"


class IdempotencyMiddleware:
    """Replay the cached response for a repeated ``Idempotency-Key`` instead of re-running it."""

    def __init__(
        self, app: ASGIApp, *, store: IdempotencyPort, ttl_seconds: int, max_body_bytes: int
    ) -> None:
        self.app = app
        self.store = store
        self.ttl_seconds = ttl_seconds
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in _MUTATING:
            await self.app(scope, receive, send)
            return
        key = _header(scope, _HEADER)
        if key is None:
            await self.app(scope, receive, send)
            return

        body, messages, over = await _buffer_body(receive, self.max_body_bytes)
        if over:
            # Too large to buffer/cache safely — pass through, streaming the rest from receive.
            log.warning("idempotency.body_too_large", path=scope["path"])
            await self.app(scope, _chain_replayer(messages, receive), send)
            return

        caller_scope = _caller_scope(scope)
        request_hash = _fingerprint(scope, body)
        result = await self.store.claim(
            key, scope=caller_scope, request_hash=request_hash, ttl_seconds=self.ttl_seconds
        )

        if result.outcome == "replay" and result.cached is not None:
            await _send_response(
                send, result.cached.status, result.cached.headers, result.cached.body
            )
            return
        if result.outcome == "in_progress":
            await _send_json(
                send, 409, "A request with this Idempotency-Key is already in progress"
            )
            return
        if result.outcome == "mismatch":
            await _send_json(send, 422, "Idempotency-Key was reused with a different request")
            return

        # outcome == "owned": run the handler exactly once, capturing its response as we stream it.
        captured = _ResponseCapture(send, self.max_body_bytes)
        try:
            await self.app(scope, _replayer(messages), captured.send)
        except Exception:
            # The handler blew up before producing a final response — drop the claim so a retry
            # isn't permanently wedged at 409, then let the error propagate to the server.
            await self.store.release(key, scope=caller_scope)
            raise
        if captured.too_big or captured.status >= 500:
            # An over-large or 5xx response is not a final, cacheable answer; release the claim.
            await self.store.release(key, scope=caller_scope)
        else:
            await self.store.complete(
                key,
                scope=caller_scope,
                status=captured.status,
                headers=captured.headers,
                body=captured.body,
            )


class _ResponseCapture:
    """Wraps ``send`` to record the outgoing status/headers/body while still streaming it."""

    def __init__(self, send: Send, max_body_bytes: int) -> None:
        self._send = send
        self._max = max_body_bytes
        self.status = 500
        self.headers: list[tuple[bytes, bytes]] = []
        self.body = b""
        self.too_big = False

    async def send(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.status = message["status"]
            self.headers = list(message.get("headers", []))
        elif message["type"] == "http.response.body":
            if not self.too_big:
                self.body += message.get("body", b"")
                if len(self.body) > self._max:
                    self.too_big = True
        await self._send(message)


async def _buffer_body(receive: Receive, max_bytes: int) -> tuple[bytes, list[Message], bool]:
    """Drain the request body (up to ``max_bytes``) so it can be fingerprinted AND replayed."""
    messages: list[Message] = []
    body = b""
    over = False
    while True:
        message = await receive()
        messages.append(message)
        if message["type"] == "http.request":
            body += message.get("body", b"")
            if len(body) > max_bytes:
                over = True
                break
            if not message.get("more_body", False):
                break
        else:  # http.disconnect
            break
    return body, messages, over


def _replayer(messages: list[Message]) -> Callable[[], Awaitable[Message]]:
    """A ``receive`` that yields the fully-buffered messages, then empty bodies."""
    queue = list(messages)

    async def receive() -> Message:
        if queue:
            return queue.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    return receive


def _chain_replayer(messages: list[Message], receive: Receive) -> Receive:
    """A ``receive`` that yields the buffered messages, then delegates to the real ``receive``."""
    queue = list(messages)

    async def _receive() -> Message:
        if queue:
            return queue.pop(0)
        return await receive()

    return _receive


def _caller_scope(scope: Scope) -> str:
    """A per-credential namespace hash so one caller's key never collides with another's.

    Derived from the (unvalidated) Authorization / API-key header, falling back to the client IP.
    Hashed, never stored raw, so no bearer tokens / API keys land in the table.
    """
    credential = _header(scope, b"authorization") or _header(scope, b"x-api-key")
    if credential is None:
        client = scope.get("client")
        credential = f"ip:{client[0]}" if client else "anonymous"
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()


def _fingerprint(scope: Scope, body: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(scope["method"].encode("ascii"))
    digest.update(b" ")
    digest.update(scope["path"].encode("utf-8"))
    digest.update(b"\n")
    digest.update(body)
    return digest.hexdigest()


def _header(scope: Scope, name: bytes) -> str | None:
    headers: list[tuple[bytes, bytes]] = scope["headers"]
    for raw_name, raw_value in headers:
        if raw_name == name:
            return raw_value.decode("latin-1")
    return None


async def _send_response(
    send: Send, status: int, headers: list[tuple[bytes, bytes]], body: bytes
) -> None:
    out = [*headers, (b"idempotent-replayed", b"true")]
    await send({"type": "http.response.start", "status": status, "headers": out})
    await send({"type": "http.response.body", "body": body})


async def _send_json(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})
