"""Typed ingress helpers for transient OpenClaw JSONL payloads."""

from __future__ import annotations

import json
from typing import NotRequired, TypedDict

from pydantic import TypeAdapter, ValidationError


class OpenClawSessionPayload(TypedDict, total=False):
    id: str
    cwd: str
    agentId: str
    title: str


class OpenClawMessageUsagePayload(TypedDict, total=False):
    inputTokens: int | float | str
    outputTokens: int | float | str
    cacheReadTokens: int | float | str
    cacheCreationTokens: int | float | str
    reasoningTokens: int | float | str


class OpenClawContentBlock(TypedDict, total=False):
    type: str
    text: str
    thinking: str
    toolCallId: str
    toolName: str
    input: dict[str, object]


class OpenClawMessagePayload(TypedDict, total=False):
    id: str
    role: str
    model: str
    toolCallId: str
    toolName: str
    isError: bool
    usage: OpenClawMessageUsagePayload
    content: list[OpenClawContentBlock]


class OpenClawModelChangePayload(TypedDict, total=False):
    model: str
    provider: str


class OpenClawThinkingLevelPayload(TypedDict, total=False):
    thinkingLevel: str


class OpenClawCustomPayload(TypedDict, total=False):
    data: dict[str, object]


OpenClawPayload = (
    OpenClawSessionPayload
    | OpenClawMessagePayload
    | OpenClawModelChangePayload
    | OpenClawThinkingLevelPayload
    | OpenClawCustomPayload
)


class OpenClawSessionLine(TypedDict):
    type: str
    timestamp: NotRequired[str | int | float]
    session: NotRequired[OpenClawSessionPayload]
    message: NotRequired[OpenClawMessagePayload]
    model: NotRequired[str]
    provider: NotRequired[str]
    thinkingLevel: NotRequired[str]
    data: NotRequired[dict[str, object]]


_OPENCLAW_SESSION_LINE_ADAPTER = TypeAdapter(OpenClawSessionLine)
_KNOWN_OPENCLAW_EVENT_TYPES = {"session", "model_change", "thinking_level_change", "custom", "message"}


def parse_openclaw_session_lines(content: str) -> list[OpenClawSessionLine]:
    """Parse a multi-line JSONL string into validated OpenClaw session line objects."""

    lines: list[OpenClawSessionLine] = []
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        if parsed.get("type") not in _KNOWN_OPENCLAW_EVENT_TYPES:
            continue
        try:
            lines.append(_OPENCLAW_SESSION_LINE_ADAPTER.validate_python(parsed))
        except ValidationError:
            continue
    return lines
