"""API-key model: hashed, org-scoped service tokens. Requires the `db` + `users` extras.

Each ``ApiKey`` belongs to an organization (the ``organizations`` table from
``app.tenancy.models``) and records the user who created it. Only the plaintext ``prefix``
(for lookup + display) and a hash of the secret are stored — never the secret itself.
The table is mapped onto the shared ``Base`` from ``app.db.models`` so a single
``Base.metadata`` covers the whole service.
"""

from __future__ import annotations

import uuid
from datetime import datetime

# Same import-ordering guard as app.tenancy.models: load fastapi_users.db before the
# adapter's `generics` submodule, or a circular init silently drops the re-exported GUID.
import fastapi_users.db  # noqa: F401  (import-ordering guard — see comment above)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    # Public lookup id (plaintext), unique so a presented key resolves to exactly one row.
    prefix: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # SHA-256 hex digest of the secret — the secret itself is never persisted.
    hashed_secret: Mapped[str] = mapped_column(String(128))
    # Space-separated scope tokens, or NULL for an unscoped key.
    scopes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
