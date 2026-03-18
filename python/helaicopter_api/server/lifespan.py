"""Application lifespan – startup / shutdown hooks."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..bootstrap.services import build_services
from .config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Attach shared state on startup; clean up on shutdown."""
    settings = Settings()
    services = build_services(settings)
    app.state.settings = settings
    app.state.services = services
    yield
    # Shutdown: dispose the SQLAlchemy engine.
    services.sqlite_engine.dispose()
