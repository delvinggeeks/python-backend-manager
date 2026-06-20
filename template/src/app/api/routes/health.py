"""Liveness / readiness."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe: report status, environment, and version."""
    settings = get_settings()
    return HealthResponse(environment=settings.environment, version=__version__)
