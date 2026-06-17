"""ASGI lifespan: wire up resources on startup, tear them down on shutdown."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info("startup", app=app.title)
    # Place pool/client init here, e.g.:
    #   from app.db.session import engine
    #   app.state.db = engine
    try:
        yield
    finally:
        log.info("shutdown")
        # Dispose pools/clients here.
