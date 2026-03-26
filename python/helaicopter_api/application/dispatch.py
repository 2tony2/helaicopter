"""Worker dispatch: registry, selection, and auth-aware filtering.

The InMemoryWorkerRegistry is the in-process mirror of registered workers.
It is rebuilt on startup from the SQLite ``worker_registry`` table and kept
in sync via heartbeat/completion events.  The ``select_worker`` function
implements provider-affinity dispatch with auth-status filtering.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# RegisteredWorker — in-memory representation
# ---------------------------------------------------------------------------


@dataclass
class RegisteredWorker:
    """In-memory snapshot of a registered worker."""

    worker_id: str
    provider: str
    models: list[str]
    status: str = "idle"  # idle | busy | draining | dead | auth_expired
    auth_status: str = "valid"  # valid | expired | unknown
    auth_credential_id: str | None = None
    current_task_id: str | None = None
    current_run_id: str | None = None
    last_heartbeat_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    max_concurrent_tasks: int = 1


# ---------------------------------------------------------------------------
# InMemoryWorkerRegistry
# ---------------------------------------------------------------------------


class InMemoryWorkerRegistry:
    """In-process worker registry for the resolver loop.

    This is the authoritative in-memory index used by the resolver for
    dispatch decisions.  It is rebuilt from SQLite on startup and updated
    by heartbeat/completion events during the loop.
    """

    def __init__(self) -> None:
        self._workers: dict[str, RegisteredWorker] = {}

    def register(
        self,
        *,
        provider: str,
        models: list[str],
        auth_status: str = "valid",
        auth_credential_id: str | None = None,
        worker_id: str | None = None,
    ) -> RegisteredWorker:
        wid = worker_id or f"wkr_{secrets.token_hex(12)}"
        worker = RegisteredWorker(
            worker_id=wid,
            provider=provider,
            models=models,
            auth_status=auth_status,
            auth_credential_id=auth_credential_id,
        )
        self._workers[wid] = worker
        return worker

    def get(self, worker_id: str) -> RegisteredWorker | None:
        return self._workers.get(worker_id)

    def all_workers(self) -> list[RegisteredWorker]:
        return list(self._workers.values())

    def idle_workers(self, *, provider: str | None = None) -> list[RegisteredWorker]:
        """Return idle workers, optionally filtered by provider."""
        result = [w for w in self._workers.values() if w.status == "idle"]
        if provider is not None:
            result = [w for w in result if w.provider == provider]
        return result

    def stale_workers(self, *, threshold: timedelta) -> list[RegisteredWorker]:
        """Return workers whose last heartbeat exceeds *threshold*."""
        cutoff = datetime.now(UTC) - threshold
        return [
            w
            for w in self._workers.values()
            if w.status in ("busy", "idle") and w.last_heartbeat_at < cutoff
        ]

    def mark_dead(self, worker_id: str) -> None:
        worker = self._workers.get(worker_id)
        if worker:
            worker.status = "dead"
            worker.current_task_id = None
            worker.current_run_id = None


# ---------------------------------------------------------------------------
# Worker selection (provider-affinity dispatch)
# ---------------------------------------------------------------------------


def select_worker(
    *,
    provider: str,
    model: str,
    registry: InMemoryWorkerRegistry,
) -> RegisteredWorker | None:
    """Select a capable idle worker for the given provider/model.

    Selection algorithm (affinity order):
      1. Provider match
      2. Model match (preferred but not required if provider matches)
      3. Auth status is valid (not expired)
      4. Worker is idle

    Returns ``None`` if no suitable worker is available.
    """
    candidates = registry.idle_workers(provider=provider)
    # Filter out auth-expired workers
    candidates = [w for w in candidates if w.auth_status != "expired"]
    if not candidates:
        return None

    # Prefer workers that explicitly list the requested model
    model_match = [w for w in candidates if model in w.models]
    if model_match:
        return model_match[0]

    # Fall back to any provider-matching worker
    return candidates[0]
