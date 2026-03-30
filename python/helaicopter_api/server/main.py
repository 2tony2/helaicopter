"""Application factory and module-level ``app`` instance."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .lifespan import lifespan
from .mcp import MCP_MOUNT_PATH, build_mcp_server
from .middleware import RequestIDMiddleware, TimingMiddleware
from .openapi import DESCRIPTION, OPENAPI_TAGS, TITLE, VERSION


def create_app() -> FastAPI:
    """Build and return a fully-configured :class:`FastAPI` application."""
    from ..router.router import root_router

    mcp_app_holder: dict[str, Any] = {}

    @asynccontextmanager
    async def combined_lifespan(application: FastAPI) -> AsyncIterator[None]:
        async with lifespan(application):
            mcp_app = mcp_app_holder["app"]
            async with mcp_app.lifespan(application):
                yield

    application = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        version=VERSION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=combined_lifespan,
    )

    # -- Middleware (outermost first) ----------------------------------------
    application.add_middleware(
        cast(Any, CORSMiddleware),
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(cast(Any, GZipMiddleware), minimum_size=1000)
    application.add_middleware(cast(Any, TimingMiddleware))
    application.add_middleware(cast(Any, RequestIDMiddleware))

    # -- Routers -------------------------------------------------------------
    application.include_router(root_router)
    mcp_server = build_mcp_server(application)
    application.state.mcp_server = mcp_server
    mcp_app = mcp_server.http_app(path="/")
    mcp_app_holder["app"] = mcp_app
    application.mount(MCP_MOUNT_PATH, mcp_app)
    return application


app: FastAPI = create_app()
