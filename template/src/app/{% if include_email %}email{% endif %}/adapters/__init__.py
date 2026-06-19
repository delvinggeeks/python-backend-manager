"""Email adapters — concrete providers behind the :class:`~app.email.ports.EmailPort`.

Each adapter wraps ONE transport (SMTP via aiosmtplib, the Amazon SES API via aioboto3) plus a
credential-free console/suppress backend for dev + tests. Exactly one is active per service,
chosen by ``settings.email_provider`` via ``app.email.provider``.
"""

from __future__ import annotations

from app.email.adapters.console import ConsoleEmailAdapter
from app.email.adapters.ses import SESAdapter
from app.email.adapters.smtp import SMTPAdapter

__all__ = ["ConsoleEmailAdapter", "SESAdapter", "SMTPAdapter"]
