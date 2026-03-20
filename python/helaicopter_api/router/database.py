"""Database status and refresh API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from helaicopter_api.application.database import (
    DatabaseOperationError,
    read_database_status,
    trigger_database_refresh,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.database import DatabaseRefreshRequest, DatabaseStatusResponse
from helaicopter_api.server.dependencies import get_services

database_router = APIRouter(prefix="/databases", tags=["databases"])


@database_router.get(
    "/status",
    response_model=DatabaseStatusResponse,
    response_model_by_alias=True,
    responses={500: {"model": DatabaseStatusResponse}},
)
async def database_status(
    services: BackendServices = Depends(get_services),
) -> DatabaseStatusResponse | JSONResponse:
    """Return database artifact status, bootstrapping refresh on first access.

    Returns:
        Status payload containing the current refresh state, timing metadata,
        runtime read-backend configuration, and per-artifact health details
        for SQLite, DuckDB, frontend cache, and Prefect Postgres.

    Raises:
        HTTPException: 500 if a database operation error occurs without a
            structured payload.
    """
    try:
        return read_database_status(services)
    except DatabaseOperationError as exc:
        if exc.payload is not None:
            return JSONResponse(
                status_code=500,
                content=exc.payload.model_dump(mode="json", by_alias=True),
            )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@database_router.post(
    "/refresh",
    response_model=DatabaseStatusResponse,
    response_model_by_alias=True,
    responses={500: {"model": DatabaseStatusResponse}},
)
async def database_refresh(
    body: DatabaseRefreshRequest = Body(default_factory=DatabaseRefreshRequest),
    services: BackendServices = Depends(get_services),
) -> DatabaseStatusResponse | JSONResponse:
    """Trigger a database refresh and invalidate backend read caches.

    Args:
        body: Refresh control options. ``force`` bypasses the staleness check
            and triggers an immediate rebuild; ``trigger`` is a label recorded
            in the refresh log (defaults to ``"manual"``);
            ``stale_after_seconds`` sets the minimum age in seconds before a
            refresh is considered necessary (defaults to 6 hours).

    Returns:
        Updated database status payload reflecting the new refresh state,
        including timing metadata and artifact health after the operation.

    Raises:
        HTTPException: 500 if a database operation error occurs without a
            structured payload.
    """
    try:
        return trigger_database_refresh(
            services,
            force=body.force,
            trigger=body.trigger,
            stale_after_seconds=body.stale_after_seconds,
        )
    except DatabaseOperationError as exc:
        if exc.payload is not None:
            return JSONResponse(
                status_code=500,
                content=exc.payload.model_dump(mode="json", by_alias=True),
            )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
