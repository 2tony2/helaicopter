from __future__ import annotations

import re
import unicodedata

_ROUTE_SLUG_MAX_LENGTH = 80
_ROUTE_SLUG_FALLBACK = "conversation"
_ROUTE_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def derive_route_slug(first_message: str) -> str:
    ascii_message = unicodedata.normalize("NFKD", first_message).encode("ascii", "ignore").decode("ascii")
    slug = _ROUTE_SLUG_PATTERN.sub("-", ascii_message.lower()).strip("-")
    slug = slug[:_ROUTE_SLUG_MAX_LENGTH].strip("-")
    return slug or _ROUTE_SLUG_FALLBACK


def build_conversation_ref(route_slug: str, provider: str, session_id: str) -> str:
    return f"{route_slug}--{provider}-{session_id}"
