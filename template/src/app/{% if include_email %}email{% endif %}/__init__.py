"""Email & notifications (provider-agnostic). Requires the `email` extra.

Email goes through a hexagonal port: ``app.email.ports.EmailPort`` is the app's-needs contract
(``send(EmailMessage)`` over a normalized, vendor-neutral message); ``app.email.adapters`` holds
the SMTP (aiosmtplib) and Amazon SES (aioboto3) implementations plus a console/suppress backend;
the active one is chosen by ``settings.email_provider`` (see ``app.email.provider``). Bodies are
rendered from jinja2 templates in ``app.email.templates`` by the typed helper in ``app.email.send``,
so callers pass a template name + context and the app never builds a vendor payload or imports a
vendor SDK outside an adapter. The heavy imports (aiosmtplib, aioboto3) live in the submodules, so
importing this package is cheap and free of import-time side effects.
"""

from __future__ import annotations
