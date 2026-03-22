"""Typed ingress helpers for transient OpenClaw JSONL payloads."""

from __future__ import annotations

import json
from typing import NotRequired, TypedDict


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


class OpenClawSessionLine(TypedDict, total=False):
    type: str
    timestamp: NotRequired[str | int | float]
    session: NotRequired[OpenClawSessionPayload]
    workspaceDir: NotRequired[str]
    message: NotRequired[OpenClawMessagePayload]
    model: NotRequired[str]
    provider: NotRequired[str]
    thinkingLevel: NotRequired[str]
    data: NotRequired[dict[str, object]]
    toolCallId: NotRequired[str]
    isError: NotRequired[bool]
    raw: NotRequired[dict[str, object]]
    unknown_fields: NotRequired[dict[str, object]]


_KNOWN_OPENCLAW_EVENT_TYPES = {
    "session",
    "message",
    "model_change",
    "thinking_level_change",
    "custom",
    "custom_message",
    "compaction",
    "branch_summary",
}
_OPENCLAW_LINE_KEYS = {
    "type",
    "timestamp",
    "session",
    "workspaceDir",
    "message",
    "model",
    "provider",
    "thinkingLevel",
    "data",
}


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
        line_type = parsed.get("type")
        if not isinstance(line_type, str) or not line_type:
            continue

        line: OpenClawSessionLine = {
            "type": line_type,
            "raw": parsed,
            "unknown_fields": {
                key: value
                for key, value in parsed.items()
                if isinstance(key, str) and key not in _OPENCLAW_LINE_KEYS
            },
        }

        timestamp = parsed.get("timestamp")
        if isinstance(timestamp, (str, int, float)):
            line["timestamp"] = timestamp

        session = parsed.get("session")
        if isinstance(session, dict):
            line["session"] = session

        workspace_dir = parsed.get("workspaceDir")
        if isinstance(workspace_dir, str):
            line["workspaceDir"] = workspace_dir

        message = parsed.get("message")
        if isinstance(message, dict):
            line["message"] = message
            if message.get("role") in {"tool", "toolResult"}:
                tool_call_id = message.get("toolCallId")
                if isinstance(tool_call_id, str) and tool_call_id:
                    line["toolCallId"] = tool_call_id
                line["isError"] = bool(message.get("isError"))

        model = parsed.get("model")
        if isinstance(model, str):
            line["model"] = model

        provider = parsed.get("provider")
        if isinstance(provider, str):
            line["provider"] = provider

        thinking_level = parsed.get("thinkingLevel")
        if isinstance(thinking_level, str):
            line["thinkingLevel"] = thinking_level

        data = parsed.get("data")
        if isinstance(data, dict):
            line["data"] = data

        if line_type not in _KNOWN_OPENCLAW_EVENT_TYPES:
            line["unknown_fields"] = {
                key: value
                for key, value in parsed.items()
                if isinstance(key, str) and key not in {"type", "timestamp"}
            }

        lines.append(line)
    return lines
