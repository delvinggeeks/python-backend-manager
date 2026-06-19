"""The typed send helper — render a template, then dispatch through an :class:`EmailPort`.

This is the app's entry point for sending mail: :func:`send_template` builds a normalized
:class:`~app.email.ports.EmailMessage` from a template name + context and sends it; :func:`send`
renders any template reference on a message and hands the result to the port. Adapters therefore
only ever receive a fully-rendered body. Requires the `email` extra.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.email.ports import EmailMessage, EmailPort
from app.email.templating import render, render_optional


def render_message(message: EmailMessage) -> EmailMessage:
    """Resolve a ``template`` reference to ``html`` / ``text``; pass a pre-rendered one through.

    ``template`` is a base name: ``"welcome"`` renders ``welcome.html`` (required) and, if it
    exists, ``welcome.txt`` as the plain-text alternative.
    """
    if message.template is None:
        return message
    context: dict[str, object] = dict(message.context or {})
    html = render(f"{message.template}.html", context)
    text = message.text or render_optional(f"{message.template}.txt", context)
    return EmailMessage(to=message.to, subject=message.subject, html=html, text=text)


async def send(provider: EmailPort, message: EmailMessage) -> None:
    """Render any template on ``message`` and deliver it through ``provider``."""
    await provider.send(render_message(message))


async def send_template(
    provider: EmailPort,
    *,
    to: str | Sequence[str],
    subject: str,
    template: str,
    context: Mapping[str, object] | None = None,
) -> None:
    """Render ``template`` with ``context`` and send it to ``to`` via ``provider``."""
    await send(provider, EmailMessage(to=to, subject=subject, template=template, context=context))
