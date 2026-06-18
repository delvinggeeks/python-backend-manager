"""Hashing, generation, and time helpers for API keys. Requires the `db` + `users` extras.

A key is rendered to the caller as ``{prefix}.{secret}`` exactly once. We persist only the
plaintext ``prefix`` (for lookup + display) and a SHA-256 hash of the high-entropy
``secret`` — never the secret itself. Unsalted SHA-256 is appropriate here precisely
because the secret is 32 random bytes from ``secrets.token_urlsafe``, not a low-entropy
human password, so it is not exposed to offline dictionary attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime

# Brand prefix stamped on every key, so a leaked token is greppable and attributable.
BRAND = "wsk"


def hash_secret(secret: str) -> str:
    """Return the SHA-256 hex digest of ``secret`` — what we store, never the raw secret."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_key() -> tuple[str, str, str]:
    """Mint a new key, returning ``(full_key, prefix, hashed_secret)``.

    ``full_key`` is ``{prefix}.{secret}`` and is shown to the caller exactly once.
    ``prefix`` is the public lookup id (e.g. ``wsk_1a2b3c4d``); ``hashed_secret`` is the
    only representation of the secret that we persist.
    """
    prefix = f"{BRAND}_{secrets.token_hex(4)}"
    secret = secrets.token_urlsafe(32)
    return f"{prefix}.{secret}", prefix, hash_secret(secret)


def split_key(raw: str) -> tuple[str, str] | None:
    """Split a presented key into ``(prefix, secret)``, or ``None`` if it is malformed.

    The ``.`` separator is unambiguous: ``token_urlsafe`` emits only ``[A-Za-z0-9_-]``, so
    the secret can never contain a dot.
    """
    prefix, sep, secret = raw.partition(".")
    if not (sep and prefix and secret):
        return None
    return prefix, secret


def verify_secret(secret: str, hashed: str) -> bool:
    """Constant-time check that ``secret`` hashes to the stored ``hashed`` value."""
    return hmac.compare_digest(hash_secret(secret), hashed)


def utcnow() -> datetime:
    """Naive UTC ``datetime`` (tzinfo stripped) — matches how timestamps are stored."""
    return datetime.now(UTC).replace(tzinfo=None)
