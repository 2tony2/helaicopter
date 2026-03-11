from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_timestamp_ms(value: int | float | None) -> datetime:
    if value is None:
        return utc_now()
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def date_key(value: date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def provider_for_project_path(project_path: str) -> str:
    return "codex" if project_path.startswith("codex:") else "claude"


def conversation_id(provider: str, session_id: str) -> str:
    return f"{provider}:{session_id}"


def tool_dim_id(provider: str, tool_name: str) -> str:
    return f"{provider}:{tool_name}"


def model_dim_id(provider: str, model_name: str) -> str:
    return f"{provider}:{model_name}"


def project_dim_id(provider: str, project_path: str) -> str:
    return f"{provider}:{project_path}"


def subagent_dim_id(provider: str, subagent_type: str) -> str:
    return f"{provider}:{subagent_type}"


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)
