"""Pure object-key helpers — no I/O, so they unit-test the tenant-isolation contract.

With tenancy, every stored key is prefixed with ``orgs/<org_id>/`` so one tenant can never
read or list another's objects; without tenancy, keys are stored verbatim. ``build_key``
maps a caller-facing key to its stored form and ``relative_key`` maps it back, so the API is
symmetric — callers always speak in their own un-prefixed keys.
"""

from __future__ import annotations


def build_key(key: str, *, org_id: str | None = None) -> str:
    """Return the stored key for ``key``, tenant-prefixed when ``org_id`` is given."""
    cleaned = key.lstrip("/")
    if org_id:
        return f"orgs/{org_id}/{cleaned}"
    return cleaned


def relative_key(stored_key: str, *, org_id: str | None = None) -> str:
    """Inverse of :func:`build_key`: strip the tenant prefix back to the caller-facing key."""
    if org_id:
        prefix = f"orgs/{org_id}/"
        if stored_key.startswith(prefix):
            return stored_key[len(prefix) :]
    return stored_key


def tenant_prefix(org_id: str | None = None) -> str:
    """Return the listing prefix that scopes results to a tenant (``""`` without tenancy)."""
    return f"orgs/{org_id}/" if org_id else ""
