"""Custom APIRoute subclasses for cross-cutting concerns."""

from __future__ import annotations

from fastapi.routing import APIRoute


class TimedRoute(APIRoute):
    """Placeholder route class that can later inject server-timing headers."""

    # No behavioural override yet – reserves the extension point.
