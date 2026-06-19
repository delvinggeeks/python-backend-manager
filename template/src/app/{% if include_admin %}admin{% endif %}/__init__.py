"""sqladmin control panel — a superuser-only admin UI mounted at /admin.

Requires the `db` + `users` + `admin` extras. ``app.main.create_app`` calls ``mount_admin(app)``
(gated on the admin capability). The panel authenticates against the user table and admits only
active superusers; its model views redact secret columns. See ``app.admin.auth`` for the
authentication backend and ``app.admin.views`` for the registered model views.
"""

from __future__ import annotations

from app.admin.setup import mount_admin

__all__ = ["mount_admin"]
