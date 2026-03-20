"""Application factory and module-level ``app`` instance."""

from __future__ import annotations

from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .lifespan import lifespan
from .middleware import RequestIDMiddleware, TimingMiddleware
from .openapi import DESCRIPTION, OPENAPI_TAGS, TITLE, VERSION


def create_app() -> FastAPI:
    """Build and return a fully-configured :class:`FastAPI` application."""
    from ..router.router import root_router

    application = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        version=VERSION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
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
    return application


app: FastAPI = create_app()
