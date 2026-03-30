"""Internal ops endpoints – health, readiness, and diagnostics."""

from __future__ import annotations

import sys
import time
from typing import Any

from fastapi import APIRouter, Depends

from ..server.config import Settings
from ..server.dependencies import get_settings
from ..server.openapi import VERSION

ops_router = APIRouter(prefix="/_ops", tags=["health"])

_BOOT_TIME = time.time()


@ops_router.get("/health")
async def ops_health() -> dict[str, str]:
    """Minimal liveness probe (no dependencies checked)."""
    return {"status": "ok"}


@ops_router.get("/ready")
async def ops_ready(
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Readiness probe that verifies critical runtime dependencies are reachable.

    Returns:
        A dict with a boolean ``ready`` field indicating overall readiness and a
        ``checks`` mapping of individual dependency names to their pass/fail status.
    """
    checks: dict[str, bool] = {
        "database_runtime_dir_exists": settings.database.runtime_dir.exists(),
    }
    all_ok = all(checks.values())
    return {"ready": all_ok, "checks": checks}


@ops_router.get("/info")
async def ops_info(
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return build and runtime metadata for dashboards and debugging.

    Returns:
        A dict containing the API version string, Python version, debug flag,
        server uptime in seconds, and the resolved project root path.
    """
    return {
        "version": VERSION,
        "python": sys.version,
        "debug": settings.debug,
        "uptime_seconds": round(time.time() - _BOOT_TIME, 1),
        "project_root": str(settings.project_root),
    }
