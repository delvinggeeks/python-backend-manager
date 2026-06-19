"""The webhook-endpoint table — a tenant's registered outbound delivery target.

Tenant-scoped (every endpoint belongs to an ``organization``). ``secret`` is the per-endpoint
HMAC-SHA256 signing key, stored in the clear because the worker must re-sign each delivery with
it; ``event_types`` is a space-separated list of subscribed event names (mirrors how
``app.api_keys`` stores scopes). Mapped onto the shared ``Base`` from ``app.db.models``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

# Load fastapi_users.db before the adapter's `generics` submodule (import-ordering guard,
# mirrors app.tenancy.models) so the GUID type imports cleanly.
import fastapi_users.db  # noqa: F401  (import-ordering guard)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class WebhookEndpoint(Base):
    """A tenant's outbound webhook target. Deliveries are signed with ``secret``."""

    __tablename__ = "webhook_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(2048))
    secret: Mapped[str] = mapped_column(String(255))
    # Space-separated subscribed event names (e.g. "member.added organization.created").
    event_types: Mapped[str] = mapped_column(String(1024))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
