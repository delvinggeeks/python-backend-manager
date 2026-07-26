"""Per-tenant rate limiting & auth-abuse protection. Requires the `cache` extra (Redis).

A ``RateLimitPort`` (:mod:`app.ratelimit.port`) backed by an atomic Redis **token bucket**
(:mod:`app.ratelimit.limiter`) — one Lua script per decision, so it is correct under concurrency
across every app instance and has no fixed-window boundary burst. It **fails open**: a Redis outage
allows traffic rather than rejecting it.

``rate_limit()`` (:mod:`app.ratelimit.dependencies`) limits a route per organization (falling
back to client IP), with the budget taken from the org's plan tier (:mod:`app.ratelimit.tiers`).
The auth helpers throttle login / refresh and lock an identity out after repeated failed logins.
Without ``REDIS_URL`` — or with ``RATELIMIT_ENABLED=false`` — the whole module no-ops.
"""

from __future__ import annotations

from app.ratelimit.dependencies import (
    assert_not_locked_out,
    clear_login_failures,
    enforce_auth_rate_limit,
    rate_limit,
    record_login_failure,
)
from app.ratelimit.port import RateLimitPort
from app.ratelimit.tiers import RateTier

__all__ = [
    "RateLimitPort",
    "RateTier",
    "assert_not_locked_out",
    "clear_login_failures",
    "enforce_auth_rate_limit",
    "rate_limit",
    "record_login_failure",
]
