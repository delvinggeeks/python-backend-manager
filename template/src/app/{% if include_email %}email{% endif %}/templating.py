"""Jinja2 rendering for email bodies. Requires the `email` extra.

Templates live in ``app/email/templates`` and ship with the package; :func:`render` turns a
template name + context into a string. HTML autoescaping is on. This is the ONLY place jinja2 is
used — adapters receive an already-rendered :class:`~app.email.ports.EmailMessage`, so no provider
code touches a template. :func:`render_optional` returns ``None`` for a missing template (used to
make the plain-text part of an email optional).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@lru_cache
def _env() -> Environment:
    """The shared jinja2 environment, loading from the package's ``templates`` directory."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(template_name: str, context: Mapping[str, object]) -> str:
    """Render ``template_name`` (e.g. ``"welcome.html"``) with ``context`` to a string."""
    return _env().get_template(template_name).render(**context)


def render_optional(template_name: str, context: Mapping[str, object]) -> str | None:
    """Like :func:`render`, but return ``None`` if the template does not exist."""
    try:
        template = _env().get_template(template_name)
    except TemplateNotFound:
        return None
    return template.render(**context)
