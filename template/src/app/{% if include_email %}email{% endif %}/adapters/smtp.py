"""SMTP email adapter (aiosmtplib) — the default provider. Requires the `email` extra.

Wraps aiosmtplib behind :class:`~app.email.ports.EmailPort`. Builds a standard-library MIME
message from the normalized :class:`~app.email.ports.EmailMessage` (text and/or HTML) and hands it
to the SMTP server from settings (host / port / credentials / TLS — never hard-coded). When no
``SMTP_HOST`` is configured the send is logged and skipped, so a dev environment never blocks on
email. Tested by injecting a fake ``sender`` — no live SMTP, no credentials.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from email.message import EmailMessage as MIMEMessage
from typing import Any

import aiosmtplib
import structlog

from app.core.config import Settings, get_settings
from app.email.ports import EmailError, EmailMessage

log = structlog.get_logger(__name__)


class SMTPAdapter:
    """Send email over SMTP via aiosmtplib (Zoho / Microsoft 365 / any host)."""

    name = "smtp"

    def __init__(
        self,
        *,
        sender: Callable[..., Awaitable[Any]] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._send = sender if sender is not None else aiosmtplib.send

    def _is_configured(self) -> bool:
        return bool(self._settings.smtp_host)

    def _sender_address(self) -> str:
        name = self._settings.email_from_name
        addr = self._settings.email_from_address
        return f"{name} <{addr}>" if name else addr

    def _build_mime(self, message: EmailMessage) -> MIMEMessage:
        mime = MIMEMessage()
        mime["From"] = self._sender_address()
        mime["To"] = ", ".join(message.recipients())
        mime["Subject"] = message.subject
        if message.text is not None:
            mime.set_content(message.text)
            if message.html is not None:
                mime.add_alternative(message.html, subtype="html")
        elif message.html is not None:
            mime.set_content(message.html, subtype="html")
        return mime

    async def send(self, message: EmailMessage) -> None:
        if message.html is None and message.text is None:
            raise EmailError("email has no body; render it via app.email.send first")
        if not self._is_configured():
            log.warning("email.smtp.unconfigured", to=message.recipients(), suppressed=True)
            return
        settings = self._settings
        await self._send(
            self._build_mime(message),
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_start_tls,
            use_tls=settings.smtp_use_tls,
        )
