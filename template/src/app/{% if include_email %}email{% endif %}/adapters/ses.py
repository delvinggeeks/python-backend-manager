"""Amazon SES email adapter (aioboto3) — the HTTP-API provider. Requires the `email` extra.

Wraps the AWS SES v2 API behind :class:`~app.email.ports.EmailPort`, mirroring the aioboto3 idiom
used by ``app.storage`` (it pairs naturally with S3-compatible storage). Builds an SES ``Simple``
content payload from the normalized :class:`~app.email.ports.EmailMessage` and sends via a per-call
client built from settings (region / credentials / endpoint — never hard-coded). With no SES
credentials the send is logged and skipped. Tested by injecting a fake aioboto3 session — no live
AWS, no credentials.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3
import structlog

from app.core.config import Settings, get_settings
from app.email.ports import EmailError, EmailMessage

log = structlog.get_logger(__name__)


class SESAdapter:
    """Send email through the Amazon SES v2 API via aioboto3."""

    name = "ses"

    def __init__(self, *, session: Any = None, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._session = session

    def _is_configured(self) -> bool:
        settings = self._settings
        return bool(settings.ses_access_key_id and settings.ses_secret_access_key)

    def _sender_address(self) -> str:
        name = self._settings.email_from_name
        addr = self._settings.email_from_address
        return f"{name} <{addr}>" if name else addr

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[Any]:
        settings = self._settings
        session = self._session or aioboto3.Session(
            aws_access_key_id=settings.ses_access_key_id,
            aws_secret_access_key=settings.ses_secret_access_key,
            region_name=settings.ses_region,
        )
        async with session.client("sesv2", endpoint_url=settings.ses_endpoint_url) as client:
            yield client

    def _content(self, message: EmailMessage) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if message.html is not None:
            body["Html"] = {"Data": message.html, "Charset": "UTF-8"}
        if message.text is not None:
            body["Text"] = {"Data": message.text, "Charset": "UTF-8"}
        subject = {"Data": message.subject, "Charset": "UTF-8"}
        return {"Simple": {"Subject": subject, "Body": body}}

    async def send(self, message: EmailMessage) -> None:
        if message.html is None and message.text is None:
            raise EmailError("email has no body; render it via app.email.send first")
        if not self._is_configured():
            log.warning("email.ses.unconfigured", to=message.recipients(), suppressed=True)
            return
        async with self._client() as client:
            await client.send_email(
                FromEmailAddress=self._sender_address(),
                Destination={"ToAddresses": message.recipients()},
                Content=self._content(message),
            )
