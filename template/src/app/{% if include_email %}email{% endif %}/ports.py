"""The provider-agnostic email/notifications CORE contract — a hexagonal *port*.

This is the app's-needs interface that the user-manager hooks and any notification code depend
on — never a vendor SDK. Concrete providers (SMTP, Amazon SES) live BEHIND it in
``app.email.adapters`` and are selected at runtime by ``settings.email_provider`` (see
``app.email.provider``). The rest of the app speaks only :class:`EmailPort` and the normalized
:class:`EmailMessage`, so swapping the provider touches no application code.

Adding a provider = implement :class:`EmailPort` in ``app.email.adapters`` and register it in
``app.email.provider`` (see the Email section of the service README). A message is either
pre-rendered (``html`` / ``text``) or a ``template`` reference + ``context`` that
``app.email.send`` renders to ``html`` / ``text`` BEFORE it reaches a port — so adapters never
touch jinja2 and only ever transmit a rendered body.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class EmailError(Exception):
    """An email cannot be sent for a config/usage reason (e.g. a message with no rendered body).

    Provider-neutral on purpose, so callers handle one error type regardless of the provider.
    """


@dataclass(frozen=True)
class EmailMessage:
    """A normalized, provider-neutral email.

    ``to`` is one address or many. A message is sendable once it has an ``html`` and/or ``text``
    body; alternatively set ``template`` (a base name like ``"welcome"``) + ``context`` and let
    :func:`app.email.send.render_message` fill the body from ``app.email.templates`` before
    dispatch. ``subject`` is always required.
    """

    to: str | Sequence[str]
    subject: str
    html: str | None = None
    text: str | None = None
    template: str | None = None
    context: Mapping[str, object] | None = None

    def recipients(self) -> list[str]:
        """The recipient list, normalized — a lone address becomes a one-element list."""
        return [self.to] if isinstance(self.to, str) else list(self.to)


@runtime_checkable
class EmailPort(Protocol):
    """The email boundary every provider adapter implements.

    ``name`` is the provider's stable key (``"smtp"`` / ``"ses"`` / ``"console"``). :meth:`send`
    transmits a RENDERED message (``html`` and/or ``text`` already resolved) and raises
    :class:`EmailError` on a usage failure it cannot suppress; an adapter whose provider is
    unconfigured logs and skips instead of raising, so a dev environment never blocks on mail.
    """

    name: str

    async def send(self, message: EmailMessage) -> None:
        """Deliver ``message`` via the provider. Raise :class:`EmailError` if it has no body."""
        ...
