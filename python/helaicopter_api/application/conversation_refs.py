from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ROUTE_SLUG_MAX_LENGTH = 80
_ROUTE_SLUG_FALLBACK = "conversation"
_ROUTE_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_KNOWN_CONVERSATION_REF_PROVIDERS = ("claude", "codex", "openclaw")


@dataclass(frozen=True)
class ConversationRouteTarget:
    provider: str
    session_id: str
    ref_session_id: str
    route_slug: str
    conversation_ref: str


def derive_route_slug(first_message: str) -> str:
    """Derive a URL-safe route slug from the first message of a conversation.

    Normalises Unicode to ASCII, lowercases, replaces non-alphanumeric
    characters with hyphens, and trims to ``_ROUTE_SLUG_MAX_LENGTH`` characters.
    Falls back to ``"conversation"`` when the result would otherwise be empty.

    Args:
        first_message: The first user message text of the conversation.

    Returns:
        A lowercase, hyphen-separated ASCII slug suitable for use in URL paths.
    """
    ascii_message = unicodedata.normalize("NFKD", first_message).encode("ascii", "ignore").decode("ascii")
    slug = _ROUTE_SLUG_PATTERN.sub("-", ascii_message.lower()).strip("-")
    slug = slug[:_ROUTE_SLUG_MAX_LENGTH].strip("-")
    return slug or _ROUTE_SLUG_FALLBACK


def build_conversation_route_target(
    route_slug: str,
    provider: str,
    session_id: str,
    *,
    ref_session_id: str | None = None,
) -> ConversationRouteTarget:
    """Construct a ``ConversationRouteTarget`` from its constituent parts.

    Args:
        route_slug: URL-safe slug derived from the conversation's first message.
        provider: Provider name (e.g. ``"claude"`` or ``"codex"``).
        session_id: The provider-specific session identifier.

    Returns:
        A frozen ``ConversationRouteTarget`` with a fully assembled
        ``conversation_ref`` string.
    """
    return ConversationRouteTarget(
        provider=provider,
        session_id=session_id,
        ref_session_id=ref_session_id or session_id,
        route_slug=route_slug,
        conversation_ref=build_conversation_ref(route_slug, provider, ref_session_id or session_id),
    )


def build_conversation_ref(route_slug: str, provider: str, session_id: str) -> str:
    """Assemble a canonical conversation reference string.

    The format is ``<route_slug>--<provider>-<session_id>``.

    Args:
        route_slug: URL-safe slug derived from the conversation's first message.
        provider: Provider name (e.g. ``"claude"`` or ``"codex"``).
        session_id: The provider-specific session identifier.

    Returns:
        A single string that uniquely identifies the conversation and can be
        round-tripped via ``parse_conversation_ref``.
    """
    return f"{route_slug}--{provider}-{session_id}"


def parse_conversation_ref(conversation_ref: str) -> ConversationRouteTarget | None:
    """Parse a conversation reference string into its constituent parts.

    Expects the format ``<route_slug>--<provider>-<session_id>`` where
    ``provider`` is one of the known values (``"claude"``, ``"codex"``).

    Args:
        conversation_ref: A fully assembled conversation reference string as
            produced by ``build_conversation_ref``.

    Returns:
        A ``ConversationRouteTarget`` when the reference is well-formed and
        the provider is recognised, otherwise ``None``.
    """
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
            ref_session_id=session_id,
            route_slug=route_slug,
            conversation_ref=conversation_ref,
        )

    return None
