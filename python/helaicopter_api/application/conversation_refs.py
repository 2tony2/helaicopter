from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ROUTE_SLUG_MAX_LENGTH = 80
_ROUTE_SLUG_FALLBACK = "conversation"
_ROUTE_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_KNOWN_CONVERSATION_REF_PROVIDERS = ("claude", "codex")


@dataclass(frozen=True)
class ConversationRouteTarget:
    provider: str
    session_id: str
    route_slug: str
    conversation_ref: str


def derive_route_slug(first_message: str) -> str:
    ascii_message = unicodedata.normalize("NFKD", first_message).encode("ascii", "ignore").decode("ascii")
    slug = _ROUTE_SLUG_PATTERN.sub("-", ascii_message.lower()).strip("-")
    slug = slug[:_ROUTE_SLUG_MAX_LENGTH].strip("-")
    return slug or _ROUTE_SLUG_FALLBACK


def build_conversation_route_target(route_slug: str, provider: str, session_id: str) -> ConversationRouteTarget:
    return ConversationRouteTarget(
        provider=provider,
        session_id=session_id,
        route_slug=route_slug,
        conversation_ref=build_conversation_ref(route_slug, provider, session_id),
    )


def build_conversation_ref(route_slug: str, provider: str, session_id: str) -> str:
    return f"{route_slug}--{provider}-{session_id}"


def parse_conversation_ref(conversation_ref: str) -> ConversationRouteTarget | None:
    route_parts = conversation_ref.rsplit("--", 1)
    if len(route_parts) != 2:
        return None

    route_slug, suffix = route_parts
    if not route_slug or not suffix:
        return None

    for provider in _KNOWN_CONVERSATION_REF_PROVIDERS:
        provider_prefix = f"{provider}-"
        if not suffix.startswith(provider_prefix):
            continue
        session_id = suffix.removeprefix(provider_prefix)
        if not session_id:
            return None
        return ConversationRouteTarget(
            provider=provider,
            session_id=session_id,
            route_slug=route_slug,
            conversation_ref=conversation_ref,
        )

    return None
