"""Console / suppress email adapter — captures messages, sends nothing. No credentials.

The dev + test backend behind :class:`~app.email.ports.EmailPort`: it records each message on
``self.sent`` (for assertions) and logs a line, but performs no SMTP/HTTP I/O. Selected when
``EMAIL_PROVIDER=console`` or ``EMAIL_SUPPRESS_SEND=true`` (see ``app.email.provider``), so a
service with no mail provider configured never sends — and tests need no network or secrets.
"""

from __future__ import annotations

import structlog

from app.email.ports import EmailMessage

log = structlog.get_logger(__name__)


class ConsoleEmailAdapter:
    """An :class:`~app.email.ports.EmailPort` that captures messages instead of sending them."""

    name = "console"

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
        log.info(
            "email.console",
            to=message.recipients(),
            subject=message.subject,
            suppressed=True,
        )
