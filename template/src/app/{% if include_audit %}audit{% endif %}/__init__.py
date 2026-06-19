"""Append-only audit log — an immutable record of meaningful events.

Any service can write an event via :func:`record`; there is intentionally no update or delete
path. The read-only, paginated list endpoint (org-scoped when tenancy is present, RBAC-gated to
admins when RBAC is present) lives in :mod:`app.audit.router`. Requires the `db` extra.
"""

from __future__ import annotations

from app.audit.service import record

__all__ = ["record"]
