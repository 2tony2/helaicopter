"""Shared backend literal vocabularies with real cross-package reuse."""

from typing import Literal

ProviderName = Literal["claude", "codex", "openclaw"]
ProviderSelection = Literal["all", "claude", "codex", "openclaw"]

EvaluationStatus = Literal["running", "completed", "failed"]
EvaluationScope = Literal["full", "failed_tool_calls", "guided_subset"]

DatabaseStatusKey = Literal["frontend_cache", "sqlite", "duckdb"]
DatabaseRole = Literal["cache", "metadata", "inspection"]
DatabaseAvailability = Literal["ready", "missing", "unreachable"]
DatabaseRefreshStatus = Literal["idle", "running", "completed", "failed"]
RuntimeReadBackend = Literal["legacy", "duckdb"]

__all__ = [
    "DatabaseAvailability",
    "DatabaseRefreshStatus",
    "DatabaseRole",
    "DatabaseStatusKey",
    "EvaluationScope",
    "EvaluationStatus",
    "ProviderName",
    "ProviderSelection",
    "RuntimeReadBackend",
]
