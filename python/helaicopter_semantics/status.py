"""Canonical orchestration status vocabulary and mapping rules.

This module re-exports the authoritative status types from helaicopter_domain
and provides mapping logic for derived display properties.
"""

from __future__ import annotations

from typing import Literal

from helaicopter_domain.vocab import RunRuntimeStatus, TaskRuntimeStatus

# Re-export canonical status types
__all__ = ["RunRuntimeStatus", "TaskRuntimeStatus", "StatusTone", "status_tone"]


StatusTone = Literal["success", "error", "warning", "info", "in_progress"]


def status_tone(status: RunRuntimeStatus | TaskRuntimeStatus) -> StatusTone:
    """Derive display tone from runtime status.

    This provides canonical UI tone mapping for orchestration statuses,
    ensuring consistent status representation across the backend and frontend.

    Args:
        status: Runtime status from OATS execution

    Returns:
        Canonical display tone for the status
    """
    if status in ("succeeded", "completed"):
        return "success"
    if status in ("failed", "timed_out"):
        return "error"
    if status in ("blocked", "skipped"):
        return "warning"
    if status in ("running", "planning"):
        return "in_progress"
    # pending
    return "info"
