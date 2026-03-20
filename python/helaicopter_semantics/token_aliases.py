"""Canonical token field alias registry.

Different API providers and historical versions of artifacts use different
field names for the same semantic token types. This module owns the
authoritative mapping rules for normalizing provider-specific token fields
into canonical vocabulary.
"""

from __future__ import annotations

from typing import Any, TypedDict


class NormalizedTokenFields(TypedDict, total=False):
    """Canonical token field names after normalization."""
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    reasoning_tokens: int


# Cache creation/write token field aliases
# These all represent tokens written to the cache (usually 5-minute TTL)
CACHE_CREATION_ALIASES = frozenset([
    "cache_creation_input_tokens",
    "cache_creation_tokens",
    "cache_write_tokens",
])

# Cache read token field aliases
# These all represent tokens read from the cache
CACHE_READ_ALIASES = frozenset([
    "cache_read_input_tokens",
    "cache_read_tokens",
])


def normalize_token_fields(raw: dict[str, Any]) -> NormalizedTokenFields:
    """Normalize provider-specific token fields into canonical vocabulary.

    This function handles the various token field aliases used by different
    providers and historical artifact versions. It enforces explicit mapping
    rules rather than silent proxy-based normalization.

    Args:
        raw: Raw token usage dictionary from an API response or artifact

    Returns:
        NormalizedTokenFields with canonical field names

    Examples:
        >>> normalize_token_fields({"input_tokens": 100, "cache_creation_input_tokens": 50})
        {'input_tokens': 100, 'cache_write_tokens': 50}

        >>> normalize_token_fields({"input_tokens": 100, "cache_read_input_tokens": 25})
        {'input_tokens': 100, 'cache_read_tokens': 25}
    """
    normalized: NormalizedTokenFields = {}

    # Standard fields pass through directly
    if "input_tokens" in raw:
        normalized["input_tokens"] = int(raw["input_tokens"])
    if "output_tokens" in raw:
        normalized["output_tokens"] = int(raw["output_tokens"])
    if "reasoning_tokens" in raw:
        normalized["reasoning_tokens"] = int(raw["reasoning_tokens"])

    # Normalize cache write tokens from various aliases
    cache_write = 0
    for alias in CACHE_CREATION_ALIASES:
        if alias in raw:
            cache_write += int(raw[alias])
    if cache_write > 0:
        normalized["cache_write_tokens"] = cache_write

    # Normalize cache read tokens from various aliases
    cache_read = 0
    for alias in CACHE_READ_ALIASES:
        if alias in raw:
            cache_read += int(raw[alias])
    if cache_read > 0:
        normalized["cache_read_tokens"] = cache_read

    return normalized
