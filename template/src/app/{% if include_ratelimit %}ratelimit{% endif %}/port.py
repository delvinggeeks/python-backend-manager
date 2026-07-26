"""The rate-limit seam — ``RateLimitPort``.

The app's dependencies depend on this contract, never a concrete limiter. The default adapter is
:class:`app.ratelimit.limiter.RedisRateLimiter` — a **token bucket evaluated as one atomic Lua
script**, so it is correct under concurrency across any number of app instances and has no
fixed-window boundary burst. A managed swap (an API gateway / edge limiter) implements the same
contract behind the ``include_ratelimit`` toggle.

Two responsibilities, deliberately on one port because they are the same subsystem, share the same
Redis, and share the same failure policy:

  * ``hit`` — the request limiter (per tenant / per client, per endpoint).
  * ``count_failure`` / ``failure_count`` / ``clear_failures`` — the consecutive-failure counter
    behind the auth lockout. An edge-gateway adapter that only limits at the edge still implements
    these against its own store; they are not optional.

**Every method MUST fail OPEN.** A limiter outage must never reject traffic: ``hit`` returns
``True`` and the counters report "nothing known" (``0``). Enforcement needs the `cache` extra and a
reachable ``REDIS_URL``; without one the whole module is an allow-everything no-op by design.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RateLimitPort(Protocol):
    """Counts requests and auth failures against a key, fail-open, for the rate-limit subsystem."""

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """``True`` if allowed; ``False`` if it exceeds ``limit`` within ``window_seconds``."""
        ...

    async def count_failure(self, key: str, *, window_seconds: int) -> int:
        """Record one failure against ``key`` and return the running count (``0`` when unknown)."""
        ...

    async def failure_count(self, key: str) -> int:
        """Read ``key``'s current failure count (``0`` when unknown / the store is unreachable)."""
        ...

    async def clear_failures(self, key: str) -> None:
        """Reset ``key``'s failure counter (e.g. after a successful login). Best-effort."""
        ...
