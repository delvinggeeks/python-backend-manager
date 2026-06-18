"""Multi-tenancy capability: organizations + memberships.

Requires the `db` + `users` extras. `app.main.create_app` mounts the `/orgs` router.
The `Organization` and `Membership` models live in `app.tenancy.models`; each membership
joins a `User` to an `Organization` and carries a free-string `role` (``owner`` /
``admin`` / ``member`` by convention) ready to be enforced by a permissions layer.
"""

from __future__ import annotations

from app.tenancy.models import ADMIN, MEMBER, OWNER, Membership, Organization

__all__ = ["ADMIN", "MEMBER", "OWNER", "Membership", "Organization"]
