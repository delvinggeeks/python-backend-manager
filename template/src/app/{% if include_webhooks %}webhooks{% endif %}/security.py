"""HMAC-SHA256 signing for outbound webhook deliveries.

Each delivery is signed with the destination endpoint's ``secret`` over the exact request
body, and the signature travels in the ``X-Webhook-Signature`` header as ``sha256=<hex>``.
A receiver verifies by recomputing the same HMAC and comparing in constant time.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Webhook-Signature"


def sign_payload(secret: str, payload: bytes) -> str:
    """Return the hex HMAC-SHA256 of ``payload`` keyed by ``secret``."""
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(secret: str, payload: bytes, signature: str) -> bool:
    """Constant-time check that ``signature`` (``sha256=<hex>`` or bare hex) matches ``payload``."""
    expected = sign_payload(secret, payload)
    candidate = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, candidate)
