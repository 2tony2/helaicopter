"""Shared backend literal vocabularies with real cross-package reuse."""

from typing import Literal

ProviderName = Literal["claude", "codex", "openclaw"]
ProviderSelection = Literal["all", "claude", "codex", "openclaw"]

EvaluationStatus = Literal["running", "completed", "failed"]
EvaluationScope = Literal["full", "failed_tool_calls", "guided_subset"]

DatabaseStatusKey = Literal["frontend_cache", "sqlite", "duckdb"]
DatabaseRole = Literal["cache", "metadata", "inspection", "orchestration"]
DatabaseAvailability = Literal["ready", "missing", "unreachable"]
DatabaseRefreshStatus = Literal["idle", "running", "completed", "failed"]
RuntimeReadBackend = Literal["legacy", "duckdb"]

TaskRuntimeStatus = Literal[
    "pending",
    "running",
    "succeeded",
    "failed",
    "timed_out",
    "skipped",
    "blocked",
]
RunRuntimeStatus = Literal[
    "pending",
    "planning",
    "running",
    "completed",
    "failed",
    "timed_out",
]

__all__ = [
    "DatabaseAvailability",
    "DatabaseRefreshStatus",
    "DatabaseRole",
    "DatabaseStatusKey",
    "EvaluationScope",
    "EvaluationStatus",
    "ProviderName",
    "ProviderSelection",
    "RunRuntimeStatus",
    "RuntimeReadBackend",
    "TaskRuntimeStatus",
]
