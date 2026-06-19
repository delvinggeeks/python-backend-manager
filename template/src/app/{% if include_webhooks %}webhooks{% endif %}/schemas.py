"""Schemas for managing webhook endpoints.

``secret`` is returned on read so a tenant can configure their receiver to verify the
signature; supply your own on create or let the server generate one. Rotate by updating it
through a fresh create (delete + recreate) — there is no separate rotate endpoint.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WebhookEndpointCreate(BaseModel):
    url: str = Field(max_length=2048)
    event_types: list[str] = Field(min_length=1)
    secret: str | None = Field(default=None, max_length=255)
    active: bool = True


class WebhookEndpointUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=2048)
    event_types: list[str] | None = Field(default=None, min_length=1)
    active: bool | None = None


class WebhookEndpointRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    url: str
    secret: str
    event_types: list[str]
    active: bool
    created_at: datetime
