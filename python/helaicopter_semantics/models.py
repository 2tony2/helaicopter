"""Canonical model matching and provider resolution.

This module owns the authoritative rules for identifying providers and
resolving model identifiers to their canonical provider and pricing category.
"""

from __future__ import annotations

from typing import Literal

ProviderIdentifier = Literal["claude", "codex"]


def resolve_provider(
    *,
    model: str | None = None,
    provider: str | None = None,
    project_path: str | None = None,
) -> ProviderIdentifier:
    """Resolve the canonical provider identifier from available metadata.

    Resolution priority:
    1. Explicit provider field (if "codex")
    2. Project path prefix (if starts with "codex:")
    3. Model identifier heuristics
    4. Default to "claude"

    Args:
        model: Model identifier string
        provider: Explicit provider field from artifact
        project_path: Project path string (may have "codex:" prefix)

    Returns:
        Canonical provider identifier
    """
    # Explicit provider field takes precedence for Codex
    if provider and provider.lower() == "codex":
        return "codex"

    # Project path prefix is authoritative
    if project_path and project_path.startswith("codex:"):
        return "codex"

    # Model identifier heuristics
    if model:
        model_lower = model.lower()
        if any(token in model_lower for token in ("gpt", "o3", "o4")):
            return "codex"

    # Default to Claude
    return "claude"
