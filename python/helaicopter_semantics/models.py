"""Canonical model matching and provider resolution.

This module owns the authoritative rules for identifying providers and
resolving model identifiers to their canonical provider and pricing category.
"""

from __future__ import annotations

from typing import Literal

ProviderIdentifier = Literal["claude", "codex", "openclaw", "opencloud"]


def resolve_provider(
    *,
    model: str | None = None,
    provider: str | None = None,
    project_path: str | None = None,
) -> ProviderIdentifier:
    """Resolve the canonical provider identifier from available metadata.

    Resolution priority:
    1. Explicit provider field (if recognized)
    2. Project path prefix (if starts with a recognized provider prefix)
    3. Model identifier heuristics
    4. Default to "claude"

    Args:
        model: Model identifier string
        provider: Explicit provider field from artifact
        project_path: Project path string (may have "codex:" prefix)

    Returns:
        Canonical provider identifier
    """
    # Explicit provider field takes precedence when recognized.
    if provider:
        provider_lower = provider.lower()
        if provider_lower in {"codex", "openclaw", "opencloud"}:
            return provider_lower

    # Project path prefix is authoritative when provenance is encoded there.
    if project_path:
        if project_path.startswith("opencloud:"):
            return "opencloud"
        if project_path.startswith("openclaw:"):
            return "openclaw"
        if project_path.startswith("codex:"):
            return "codex"

    # Model identifier heuristics
    if model:
        model_lower = model.lower()
        if any(token in model_lower for token in ("gpt", "o3", "o4")):
            return "codex"

    # Default to Claude
    return "claude"
