"""Typed ingress helpers for transient Codex JSON payloads."""

from __future__ import annotations

import json
from typing import NotRequired, TypedDict

from pydantic import TypeAdapter, ValidationError


class CodexContentBlock(TypedDict, total=False):
    type: str
    text: str


class CodexReasoningSummaryBlock(TypedDict, total=False):
    type: str
    text: str


class CodexUpdatePlanStep(TypedDict, total=False):
    step: str
    status: str


class CodexUpdatePlanArguments(TypedDict, total=False):
    explanation: str
    plan: list[CodexUpdatePlanStep]


class CodexSpawnAgentArguments(TypedDict, total=False):
    message: str
    agent_type: str


class CodexSpawnAgentOutput(TypedDict, total=False):
    agent_id: str
    agentId: str
    id: str
    nickname: str


class CodexThreadSpawn(TypedDict, total=False):
    parent_thread_id: str


class CodexSubagentSource(TypedDict, total=False):
    thread_spawn: CodexThreadSpawn


class CodexSessionSource(TypedDict, total=False):
    subagent: CodexSubagentSource


class CodexTotalTokenUsage(TypedDict, total=False):
    input_tokens: int | float | str
    cached_input_tokens: int | float | str
    output_tokens: int | float | str
    reasoning_output_tokens: int | float | str


class CodexTokenCountInfo(TypedDict, total=False):
    total_token_usage: CodexTotalTokenUsage


class CodexSessionMetaPayload(TypedDict, total=False):
    id: str
    cwd: str
    source: str | CodexSessionSource
    agent_role: str


class CodexTurnContextPayload(TypedDict, total=False):
    model: str
    reasoning_effort: str


class CodexWebSearchAction(TypedDict, total=False):
    type: str
    query: str
    queries: list[str]


class CodexResponseItemPayload(TypedDict, total=False):
    type: str
    role: str
    name: str
    call_id: str
    arguments: str | dict[str, object]
    output: str
    input: str
    content: list[CodexContentBlock]
    summary: list[CodexReasoningSummaryBlock]
    action: CodexWebSearchAction
    status: str


class CodexEventMsgPayload(TypedDict, total=False):
    type: str
    info: CodexTokenCountInfo


CodexPayload = (
    CodexSessionMetaPayload
    | CodexTurnContextPayload
    | CodexResponseItemPayload
    | CodexEventMsgPayload
)


class CodexSessionLine(TypedDict):
    type: str
    timestamp: NotRequired[str | int | float]
    payload: NotRequired[CodexPayload]


_CODEX_SESSION_LINE_ADAPTER = TypeAdapter(CodexSessionLine)
_CODEX_UPDATE_PLAN_ARGUMENTS_ADAPTER = TypeAdapter(CodexUpdatePlanArguments)
_CODEX_SPAWN_AGENT_ARGUMENTS_ADAPTER = TypeAdapter(CodexSpawnAgentArguments)
_CODEX_SPAWN_AGENT_OUTPUT_ADAPTER = TypeAdapter(CodexSpawnAgentOutput)
_CODEX_SESSION_SOURCE_ADAPTER = TypeAdapter(CodexSessionSource)


def parse_codex_session_lines(content: str) -> list[CodexSessionLine]:
    lines: list[CodexSessionLine] = []
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
            lines.append(_CODEX_SESSION_LINE_ADAPTER.validate_python(parsed))
        except (ValidationError, json.JSONDecodeError):
            continue
    return lines


def parse_codex_update_plan_arguments(raw_value: object) -> CodexUpdatePlanArguments | None:
    return _parse_json_mapping(raw_value, _CODEX_UPDATE_PLAN_ARGUMENTS_ADAPTER)


def parse_codex_spawn_agent_arguments(raw_value: object) -> CodexSpawnAgentArguments | None:
    return _parse_json_mapping(raw_value, _CODEX_SPAWN_AGENT_ARGUMENTS_ADAPTER)


def parse_codex_spawn_agent_output(raw_value: object) -> CodexSpawnAgentOutput | None:
    return _parse_json_mapping(raw_value, _CODEX_SPAWN_AGENT_OUTPUT_ADAPTER)


def parse_codex_session_source(raw_value: object) -> CodexSessionSource | None:
    if not raw_value:
        return None
    if isinstance(raw_value, str):
        return _parse_json_mapping(raw_value, _CODEX_SESSION_SOURCE_ADAPTER)
    try:
        return _CODEX_SESSION_SOURCE_ADAPTER.validate_python(raw_value)
    except ValidationError:
        return None


def payload_for_line(line: CodexSessionLine) -> CodexPayload:
    payload = line.get("payload")
    if payload is None:
        return {}
    return payload


def _parse_json_mapping[T](raw_value: object, adapter: TypeAdapter[T]) -> T | None:
    if isinstance(raw_value, str):
        if not raw_value.strip():
            return None
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return None
    else:
        parsed = raw_value

    try:
        return adapter.validate_python(parsed)
    except ValidationError:
        return None
