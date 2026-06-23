"""Best-effort Redis denylist for access-token JTIs (single-session logout).

Requires the `cache` extra + ``REDIS_URL`` to actually deny a token. With neither, it no-ops
(logging a warning on write) so the no-infra path still authenticates — single-session
revocation then degrades to the access token's natural (short) expiry. Logout-*everywhere*
does not rely on this: it bumps ``User.token_version`` in the DB and works without Redis.

Reads fail OPEN (no Redis / error → "not denied") so an auth check never hard-fails on a
denylist outage; the short access-token lifetime bounds the exposure window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

_logger = get_logger(__name__)
_client: Redis | None = None


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
    # Tight timeouts: the denylist is on the auth hot path, so a slow/unreachable Redis must
    # fail fast (and be swallowed) rather than stall every authenticated request.
    _client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.25,
        socket_timeout=0.25,
    )
    return _client


async def deny_jti(jti: str, ttl_seconds: int) -> None:
    """Best-effort: mark an access-token jti revoked until it would have expired anyway."""
    client = _redis_client()
    if client is None:
        _logger.warning(
            "access-token denylist disabled (no Redis) — single-session logout is best-effort; "
            "logout-everywhere (token_version) is unaffected"
        )
        return
    try:
        await client.set(f"denylist:jti:{jti}", "1", ex=max(ttl_seconds, 1))
    except Exception as exc:
        # A denylist outage must never make logout 500 — degrade to natural expiry.
        _logger.warning("denylist write failed (ignored)", error=str(exc))


async def is_jti_denied(jti: str) -> bool:
    """Best-effort: True iff the jti is denylisted. Fails OPEN (no Redis / error → not denied)."""
    client = _redis_client()
    if client is None:
        return False
    try:
        return bool(await client.exists(f"denylist:jti:{jti}"))
    except Exception as exc:
        _logger.warning("denylist read failed (ignored)", error=str(exc))
        return False
