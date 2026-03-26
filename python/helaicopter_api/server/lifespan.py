"""Application lifespan – startup / shutdown hooks."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..application.dispatch import InMemoryWorkerRegistry
from ..application.resolver import ResolverLoop
from ..bootstrap.services import build_services
from .config import Settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Attach shared state on startup; clean up on shutdown."""
    settings = Settings()
    services = build_services(settings)
    app.state.settings = settings
    app.state.services = services

    # Start the resolver loop as a background task.
    registry = InMemoryWorkerRegistry()
    resolver = ResolverLoop(
        registry=registry,
        sqlite_engine=services.sqlite_engine,
        runtime_dir=settings.runtime_dir,
    )
    app.state.resolver = resolver
    app.state.worker_registry = registry
    resolver_task = asyncio.create_task(resolver.run())

    yield

    # Shutdown: stop resolver loop, then dispose engine.
    resolver.stop()
    resolver_task.cancel()
    try:
        await resolver_task
    except asyncio.CancelledError:
        pass
    services.sqlite_engine.dispose()
