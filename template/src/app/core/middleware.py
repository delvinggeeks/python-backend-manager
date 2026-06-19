"""Cross-cutting ASGI middleware — security response headers.

A pure-ASGI middleware (not Starlette's ``BaseHTTPMiddleware``) so it adds headers without buffering
the body or interfering with streaming/background tasks. It sets the standard hardening headers on
every HTTP response with ``setdefault``, so an upstream proxy or a route that already set a value
wins. HSTS is emitted only when ``include_hsts`` is true (production over HTTPS) — sending it over
plain-HTTP dev would be wrong. The default CSP only forbids framing, so it never breaks ``/docs`` or
``/admin``; a service that serves its own HTML can tighten ``security_csp``.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Add standard hardening headers (nosniff, frame-deny, referrer, CSP, HSTS) to responses."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        csp: str,
        hsts_max_age: int,
        include_hsts: bool,
    ) -> None:
        self.app = app
        self.csp = csp
        self.hsts_max_age = hsts_max_age
        self.include_hsts = include_hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("x-content-type-options", "nosniff")
                headers.setdefault("x-frame-options", "DENY")
                headers.setdefault("referrer-policy", "strict-origin-when-cross-origin")
                if self.csp:
                    headers.setdefault("content-security-policy", self.csp)
                if self.include_hsts:
                    headers.setdefault(
                        "strict-transport-security",
                        f"max-age={self.hsts_max_age}; includeSubDomains",
                    )
            await send(message)

        await self.app(scope, receive, send_with_headers)
