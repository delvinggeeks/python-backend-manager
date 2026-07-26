"""Redis token-bucket rate limiter — the default ``RateLimitPort`` adapter. Atomic + fail-open.

Production-grade: each decision is a single **atomic Lua script** (EVALSHA), so it is correct under
high concurrency across any number of app instances, has no fixed-window boundary-burst, and no
INCR/EXPIRE race that could leak a key with no TTL. Time comes from the **Redis server clock**
(`TIME`) so multiple app hosts agree without clock-skew. Idle buckets expire (bounded key growth).

Like the auth denylist, it **fails OPEN**: no Redis (the `cache` extra absent / ``REDIS_URL`` unset)
or any error → the request is allowed, with a tightly-timed-out client so a slow Redis can't
stall the hot path. The bucket holds ``limit`` tokens and refills at ``limit / window_seconds``
tokens/second — ``limit`` requests per window sustained, burst up to a full bucket.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

log = get_logger(__name__)
_client: Redis | None = None

# Atomic token-bucket. KEYS[1]=bucket; ARGV: rate (tokens/sec), burst (max tokens), ttl (sec).
# Uses the Redis server clock so app hosts agree. Returns 1 (allowed) / 0 (limited).
_BUCKET_LUA = """
local rate = tonumber(ARGV[1])
local burst = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
local data = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
  tokens = burst
  ts = now
end
tokens = math.min(burst, tokens + math.max(0, now - ts) * rate)
local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', KEYS[1], ttl)
return allowed
"""

# Atomic INCR-with-EXPIRE for failure counters (no leaked-key race). Returns the running count.
_INCR_LUA = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1])) end
return c
"""


def _redis_client() -> Redis | None:
    """Return a cached Redis client, or None if the `cache` extra is absent / REDIS_URL is unset."""
    global _client
    if _client is not None:
        return _client
    settings = get_settings()
    if settings.redis_url is None:
        return None
    try:
        from redis.asyncio import Redis
    except ModuleNotFoundError:
        return None
    # Tight timeouts: rate-limiting is on the request hot path, so a slow/unreachable Redis must
    # fail fast (and be swallowed → allow) rather than stall every request.
    _client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.25,
        socket_timeout=0.25,
    )
    return _client


class RedisRateLimiter:
    """Atomic token-bucket limiter over Redis; fails OPEN on any error or when Redis is absent."""

    def __init__(self) -> None:
        # Lazily-registered Lua scripts (EVALSHA, with EVAL fallback handled by redis-py).
        self._bucket: Any = None
        self._incr: Any = None

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Consume one token from ``key``'s bucket; ``True`` if allowed, ``False`` if exhausted.

        Fails OPEN: no Redis or any error → ``True`` (a limiter outage must never reject traffic).
        """
        client = _redis_client()
        if client is None:
            return True
        try:
            if self._bucket is None:
                self._bucket = client.register_script(_BUCKET_LUA)
            rate = limit / window_seconds
            allowed = await self._bucket(
                keys=[f"ratelimit:{key}"],
                args=[rate, limit, window_seconds * 2],
            )
            return bool(int(allowed))
        except Exception as exc:  # any Redis failure must degrade open, not reject
            log.warning("ratelimit.redis_error_ignored", error=str(exc))
            return True

    async def count_failure(self, key: str, *, window_seconds: int) -> int:
        """Atomically record one failure (e.g. a bad login) against ``key``; return the count.

        Used for auth lockout. Fails OPEN (returns 0 — "no failures known") on any error.
        """
        count = await self._incr_with_ttl(f"ratelimit:fail:{key}", window_seconds)
        return count if count is not None else 0

    async def failure_count(self, key: str) -> int:
        """Read the current failure count for ``key`` (for the lockout check). Fail-open → 0."""
        client = _redis_client()
        if client is None:
            return 0
        try:
            raw = await client.get(f"ratelimit:fail:{key}")
            return int(raw) if raw is not None else 0
        except Exception as exc:
            log.warning("ratelimit.redis_error_ignored", error=str(exc))
            return 0

    async def clear_failures(self, key: str) -> None:
        """Reset the failure counter for ``key`` (e.g. after a successful login). Best-effort."""
        client = _redis_client()
        if client is None:
            return
        try:
            await client.delete(f"ratelimit:fail:{key}")
        except Exception as exc:
            log.warning("ratelimit.redis_error_ignored", error=str(exc))

    async def _incr_with_ttl(self, full_key: str, window_seconds: int) -> int | None:
        client = _redis_client()
        if client is None:
            return None
        try:
            if self._incr is None:
                self._incr = client.register_script(_INCR_LUA)
            return int(await self._incr(keys=[full_key], args=[window_seconds]))
        except Exception as exc:
            log.warning("ratelimit.redis_error_ignored", error=str(exc))
            return None
