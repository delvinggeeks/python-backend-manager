"""The enqueue seam — submit background jobs without importing arq at the call site.

Routes/services call :func:`enqueue` with a task *name* and its args; the arq Redis pool is
built lazily from settings (REDIS_URL) and cached per process. :func:`redis_settings` is the
single source of the connection config, shared with the worker. Tests monkeypatch
:func:`get_pool` with an in-memory fake, so the seam is exercised without a live Redis.
Requires the `worker` extra (arq).
"""

from __future__ import annotations

from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    """arq Redis connection settings from REDIS_URL (falls back to localhost:6379)."""
    redis_url = get_settings().redis_url
    return RedisSettings.from_dsn(redis_url) if redis_url else RedisSettings()


async def get_pool() -> ArqRedis:
    """Return the process-wide arq Redis pool, opening it on first use. The seam tests patch."""
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue(task: str, *args: Any, **kwargs: Any) -> bool:
    """Enqueue ``task`` (a registered arq function name) for the worker to run.

    The one place the app hands work to the queue — call sites pass a name + args and never
    import arq. Best-effort by design: a queue outage must not break the request that scheduled
    the job (the resilience the queue exists to provide), so an unreachable Redis is logged and
    swallowed rather than raised — mirroring how the email provider no-ops when unconfigured.
    Returns ``True`` when the job was queued, ``False`` when the backend was unreachable.
    """
    try:
        pool = await get_pool()
        await pool.enqueue_job(task, *args, **kwargs)
    except (OSError, RedisError) as exc:
        log.warning("jobs.enqueue_failed", task=task, error=str(exc))
        return False
    return True
