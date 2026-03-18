"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from ..bootstrap.services import BackendServices
from .config import Settings


def get_settings(request: Request) -> Settings:
    """Retrieve the ``Settings`` instance stored on ``app.state``."""
    return request.app.state.settings  # type: ignore[no-any-return]


def get_services(request: Request) -> BackendServices:
    """Retrieve the ``BackendServices`` bag stored on ``app.state``."""
    return request.app.state.services  # type: ignore[no-any-return]
