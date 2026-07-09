from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from helaicopter_api.server.config import Settings
from helaicopter_db import export_pipeline


def _create_hermes_state_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE sessions (
              id TEXT PRIMARY KEY,
              source TEXT NOT NULL,
              user_id TEXT,
              model TEXT,
              model_config TEXT,
              system_prompt TEXT,
              parent_session_id TEXT,
              started_at REAL NOT NULL,
              ended_at REAL,
              end_reason TEXT,
              message_count INTEGER DEFAULT 0,
              tool_call_count INTEGER DEFAULT 0,
              input_tokens INTEGER DEFAULT 0,
              output_tokens INTEGER DEFAULT 0,
              cache_read_tokens INTEGER DEFAULT 0,
              cache_write_tokens INTEGER DEFAULT 0,
              reasoning_tokens INTEGER DEFAULT 0,
              billing_provider TEXT,
              billing_base_url TEXT,
              billing_mode TEXT,
              estimated_cost_usd REAL,
              actual_cost_usd REAL,
              cost_status TEXT,
              cost_source TEXT,
              pricing_version TEXT,
              title TEXT,
              api_call_count INTEGER DEFAULT 0
            );

            CREATE TABLE messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id TEXT NOT NULL REFERENCES sessions(id),
              role TEXT NOT NULL,
              content TEXT,
              tool_call_id TEXT,
              tool_calls TEXT,
              tool_name TEXT,
              timestamp REAL NOT NULL,
              token_count INTEGER,
              finish_reason TEXT,
              reasoning TEXT,
              reasoning_content TEXT,
              reasoning_details TEXT,
              codex_reasoning_items TEXT,
              codex_message_items TEXT
            );
            """
        )
        connection.execute(
            """
            INSERT INTO sessions (
              id, source, model, started_at, ended_at, message_count,
              tool_call_count, input_tokens, output_tokens, cache_read_tokens,
              cache_write_tokens, reasoning_tokens, estimated_cost_usd, title
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "hermes-session-1",
                "discord",
                "gpt-5.1",
                1_710_000_000.0,
                1_710_000_090.0,
                3,
                3,
                120,
                45,
                7,
                3,
                11,
                0.0123,
                "Synthetic Hermes title",
            ),
        )
        connection.execute(
            """
            INSERT INTO messages (session_id, role, content, timestamp, token_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("hermes-session-1", "user", "synthetic user request", 1_710_000_001.0, 12),
        )
        connection.execute(
            """
            INSERT INTO messages (session_id, role, content, tool_calls, timestamp, token_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "hermes-session-1",
                "assistant",
                "synthetic assistant response",
                json.dumps(
                    [
                        {"id": "call-1", "function": {"name": "terminal", "arguments": {"cmd": "true"}}},
                        {"id": "call-2", "name": "read_file", "input": {"path": "/tmp/example"}},
                    ]
                ),
                1_710_000_030.0,
                20,
            ),
        )
        connection.execute(
            """
            INSERT INTO messages (session_id, role, content, tool_call_id, tool_name, timestamp, token_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("hermes-session-1", "tool", "synthetic tool output", "call-1", "terminal", 1_710_000_040.0, 8),
        )
        connection.commit()
    finally:
        connection.close()


def _envelope(session_id: str, *, timestamp: int, input_tokens: int) -> dict[str, object]:
    return {
        "type": "conversation",
        "summary": {
            "sessionId": session_id,
            "provider": "claude",
            "projectPath": "-Users-tony-Code-helaicopter",
            "projectName": "helaicopter",
            "threadType": "main",
            "firstMessage": f"session {session_id}",
            "timestamp": timestamp,
            "messageCount": 1,
            "model": "claude-sonnet-4-5-20250929",
            "totalInputTokens": input_tokens,
            "totalOutputTokens": 0,
            "totalCacheCreationTokens": 0,
            "totalCacheReadTokens": 0,
            "totalReasoningTokens": 0,
            "toolUseCount": 0,
            "subagentCount": 0,
            "taskCount": 0,
            "toolBreakdown": {},
            "subagentTypeBreakdown": {},
            "recordSource": f"/tmp/{session_id}.jsonl",
            "sourceFileModifiedAt": timestamp + 1_000,
        },
        "detail": {
            "endTime": timestamp + 60_000,
            "messages": [],
            "plans": [],
            "subagents": [],
            "contextAnalytics": {"buckets": [], "steps": []},
        },
        "tasks": [],
        "cost": {
            "inputCost": 0.1,
            "outputCost": 0.0,
            "cacheWriteCost": 0.0,
            "cacheReadCost": 0.0,
            "totalCost": 0.1,
        },
    }


def _stable(value: object) -> object:
    if isinstance(value, list):
        return [_stable(item) for item in value]
    if isinstance(value, dict):
        return {key: _stable(value[key]) for key in sorted(value)}
    return value


def _stub_empty_hermes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        export_pipeline,
        "_iter_hermes_historical_envelopes",
        lambda _settings: iter(()),
        raising=False,
    )


def test_iter_export_rows_uses_python_collectors_without_tsx(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = Settings(project_root=tmp_path)
    expected = [
        _envelope("session-a", timestamp=1_710_000_000_000, input_tokens=100),
        _envelope("session-b", timestamp=1_710_000_600_000, input_tokens=200),
    ]

    monkeypatch.setattr(
        export_pipeline,
        "_iter_claude_historical_envelopes",
        lambda _settings: iter(expected[:1]),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_codex_historical_envelopes",
        lambda _settings: iter(expected[1:]),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_openclaw_historical_envelopes",
        lambda _settings: iter(()),
        raising=False,
    )
    _stub_empty_hermes(monkeypatch)
    monkeypatch.setattr(
        export_pipeline,
        "tsx_binary",
        lambda _settings=None: (_ for _ in ()).throw(AssertionError("tsx should not be invoked")),
        raising=False,
    )

    assert list(export_pipeline.iter_export_rows(settings)) == expected


def test_read_export_meta_hashes_python_historical_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = Settings(project_root=tmp_path)
    envelopes = [
        _envelope("session-b", timestamp=1_710_000_600_000, input_tokens=200),
        _envelope("session-a", timestamp=1_710_000_000_000, input_tokens=100),
    ]

    monkeypatch.setattr(
        export_pipeline,
        "_iter_claude_historical_envelopes",
        lambda _settings: iter(envelopes[:1]),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_codex_historical_envelopes",
        lambda _settings: iter(envelopes[1:]),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_openclaw_historical_envelopes",
        lambda _settings: iter(()),
        raising=False,
    )
    _stub_empty_hermes(monkeypatch)
    monkeypatch.setattr(
        export_pipeline,
        "tsx_binary",
        lambda _settings=None: (_ for _ in ()).throw(AssertionError("tsx should not be invoked")),
        raising=False,
    )
    monkeypatch.setattr(export_pipeline, "_utc_now_ms", lambda: 1_710_086_400_000, raising=False)

    meta = export_pipeline.read_export_meta(settings)

    sorted_summaries = sorted(
        (_stable(envelope["summary"]) for envelope in envelopes),
        key=lambda item: json.dumps(item, sort_keys=True),
    )
    expected_input_key = hashlib.sha256(json.dumps(sorted_summaries).encode("utf-8")).hexdigest()
    cutoff_start = 1_710_086_400_000 - 365 * 24 * 60 * 60 * 1000
    expected_window_start = datetime.fromtimestamp(
        max(cutoff_start, 1_710_000_000_000) / 1000,
        tz=UTC,
    ).isoformat().replace("+00:00", "Z")

    assert meta.conversation_count == 2
    assert meta.input_key == expected_input_key
    assert meta.window_days == 365
    assert meta.window_start == expected_window_start
    assert meta.window_end == datetime.fromtimestamp(1_710_086_400_000 / 1000, tz=UTC).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    ).isoformat().replace("+00:00", "Z")


def test_iter_export_rows_omits_optional_null_fields_before_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = Settings(project_root=tmp_path)
    envelope = _envelope("session-a", timestamp=1_710_000_000_000, input_tokens=100)
    envelope["summary"]["reasoningEffort"] = None
    envelope["detail"]["messages"] = [
        {
            "role": "user",
            "timestamp": 1_710_000_000_000,
            "model": None,
            "reasoningTokens": 0,
            "speed": None,
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            "blocks": [{"type": "text", "text": "hello"}],
        }
    ]

    monkeypatch.setattr(
        export_pipeline,
        "_iter_claude_historical_envelopes",
        lambda _settings: iter([envelope]),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_codex_historical_envelopes",
        lambda _settings: iter(()),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_openclaw_historical_envelopes",
        lambda _settings: iter(()),
        raising=False,
    )
    _stub_empty_hermes(monkeypatch)

    rows = list(export_pipeline.iter_export_rows(settings))

    assert len(rows) == 1
    summary = rows[0]["summary"]
    message = rows[0]["detail"]["messages"][0]
    assert "reasoningEffort" not in summary
    assert "model" not in message
    assert "speed" not in message


def test_iter_export_rows_deduplicates_same_conversation_key_to_latest_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = Settings(project_root=tmp_path)
    older = _envelope("session-a", timestamp=1_710_000_000_000, input_tokens=100)
    newer = _envelope("session-a", timestamp=1_710_000_100_000, input_tokens=200)
    older["summary"]["sourceFileModifiedAt"] = 10
    older["summary"]["recordSource"] = "/tmp/older.jsonl"
    older["summary"]["sourcePath"] = "/tmp/older.jsonl"
    newer["summary"]["sourceFileModifiedAt"] = 20
    newer["summary"]["recordSource"] = "/tmp/newer.jsonl"
    newer["summary"]["sourcePath"] = "/tmp/newer.jsonl"

    monkeypatch.setattr(
        export_pipeline,
        "_iter_claude_historical_envelopes",
        lambda _settings: iter([older, newer]),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_codex_historical_envelopes",
        lambda _settings: iter(()),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_openclaw_historical_envelopes",
        lambda _settings: iter(()),
        raising=False,
    )
    _stub_empty_hermes(monkeypatch)

    rows = list(export_pipeline.iter_export_rows(settings))

    assert len(rows) == 1
    assert rows[0]["summary"]["totalInputTokens"] == 200
    assert rows[0]["summary"]["recordSource"] == "/tmp/newer.jsonl"


def test_iter_export_rows_includes_openclaw_historical_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = Settings(project_root=tmp_path)
    claude = _envelope("session-a", timestamp=1_710_000_000_000, input_tokens=100)
    openclaw = _envelope("session-openclaw", timestamp=1_710_000_600_000, input_tokens=50)
    openclaw["summary"]["provider"] = "openclaw"
    openclaw["summary"]["projectPath"] = "openclaw:agent:main"
    openclaw["summary"]["projectName"] = "openclaw:agent:main"
    openclaw["summary"]["recordSource"] = "/tmp/openclaw-session.jsonl"
    openclaw["summary"]["sourcePath"] = "/tmp/openclaw-session.jsonl"

    monkeypatch.setattr(
        export_pipeline,
        "_iter_claude_historical_envelopes",
        lambda _settings: iter([claude]),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_codex_historical_envelopes",
        lambda _settings: iter(()),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_openclaw_historical_envelopes",
        lambda _settings: iter([openclaw]),
        raising=False,
    )
    _stub_empty_hermes(monkeypatch)

    rows = list(export_pipeline.iter_export_rows(settings))

    assert [row["summary"]["sessionId"] for row in rows] == ["session-a", "session-openclaw"]
    assert rows[1]["summary"]["provider"] == "openclaw"


def test_iter_hermes_historical_envelopes_reads_state_db(tmp_path: Path) -> None:
    hermes_db_path = tmp_path / ".hermes" / "state.db"
    _create_hermes_state_db(hermes_db_path)
    settings = Settings(project_root=tmp_path, hermes_dir=tmp_path / ".hermes")

    rows = list(export_pipeline._iter_hermes_historical_envelopes(settings))

    assert len(rows) == 1
    row = rows[0]
    summary = row["summary"]
    assert summary["provider"] == "hermes"
    assert summary["sessionId"] == "hermes-session-1"
    assert summary["projectPath"] == "hermes:discord"
    assert summary["projectName"] == "Hermes Discord"
    assert summary["threadType"] == "main"
    assert summary["firstMessage"] == "Synthetic Hermes title"
    assert summary["timestamp"] == 1_710_000_000_000
    assert summary["messageCount"] == 3
    assert summary["model"] == "gpt-5.1"
    assert summary["totalInputTokens"] == 120
    assert summary["totalOutputTokens"] == 45
    assert summary["totalCacheCreationTokens"] == 3
    assert summary["totalCacheReadTokens"] == 7
    assert summary["totalReasoningTokens"] == 11
    assert summary["toolUseCount"] == 3
    assert summary["toolBreakdown"] == {"read_file": 1, "terminal": 2}
    assert summary["recordSource"] == str(hermes_db_path)
    assert row["cost"]["totalCost"] == pytest.approx(0.0123)
    assert row["detail"]["endTime"] == 1_710_000_090_000
    assert [message["role"] for message in row["detail"]["messages"]] == ["user", "assistant", "tool"]
    assert row["detail"]["messages"][1]["blocks"][1:] == [
        {
            "type": "tool_call",
            "toolUseId": "call-1",
            "toolName": "terminal",
            "input": {"cmd": "true"},
            "result": None,
            "isError": None,
        },
        {
            "type": "tool_call",
            "toolUseId": "call-2",
            "toolName": "read_file",
            "input": {"path": "/tmp/example"},
            "result": None,
            "isError": None,
        },
    ]


def test_iter_hermes_historical_envelopes_ignores_missing_state_db(tmp_path: Path) -> None:
    settings = Settings(project_root=tmp_path, hermes_dir=tmp_path / ".hermes")

    assert list(export_pipeline._iter_hermes_historical_envelopes(settings)) == []


def test_iter_export_rows_preserves_openclaw_provider_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = Settings(project_root=tmp_path)
    claude = _envelope("shared-session", timestamp=1_710_000_000_000, input_tokens=100)
    openclaw = _envelope("shared-session", timestamp=1_710_000_100_000, input_tokens=200)
    openclaw["summary"]["provider"] = "openclaw"
    openclaw["summary"]["projectPath"] = "openclaw:agent:secondary"
    openclaw["summary"]["projectName"] = "openclaw:agent:secondary"
    openclaw["summary"]["recordSource"] = "/tmp/openclaw-shared.jsonl"
    openclaw["summary"]["sourcePath"] = "/tmp/openclaw-shared.jsonl"

    monkeypatch.setattr(
        export_pipeline,
        "_iter_claude_historical_envelopes",
        lambda _settings: iter([claude]),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_codex_historical_envelopes",
        lambda _settings: iter(()),
        raising=False,
    )
    monkeypatch.setattr(
        export_pipeline,
        "_iter_openclaw_historical_envelopes",
        lambda _settings: iter([openclaw]),
        raising=False,
    )
    _stub_empty_hermes(monkeypatch)

    rows = list(export_pipeline.iter_export_rows(settings))

    assert len(rows) == 2
    by_provider = {row["summary"]["provider"]: row for row in rows}
    assert by_provider["claude"]["summary"]["projectPath"] == "-Users-tony-Code-helaicopter"
    assert by_provider["openclaw"]["summary"]["projectPath"] == "openclaw:agent:secondary"


def test_build_envelope_omits_unknown_openclaw_costs() -> None:
    summary = export_pipeline.ConversationSummaryResponse(
        session_id="session-openclaw",
        project_path="openclaw:agent:main",
        project_name="openclaw:agent:main",
        route_slug="unknown-openclaw-pricing",
        conversation_ref="unknown-openclaw-pricing--openclaw-session-openclaw",
        thread_type="main",
        first_message="Unknown OpenClaw pricing",
        timestamp=1_710_000_600_000,
        created_at=1_710_000_600_000,
        last_updated_at=1_710_000_660_000,
        is_running=False,
        message_count=1,
        model="openclaw-internal-preview",
        total_input_tokens=50_000,
        total_output_tokens=5_000,
        total_cache_creation_tokens=1_000,
        total_cache_read_tokens=2_000,
        tool_use_count=0,
        failed_tool_call_count=0,
        tool_breakdown={},
        subagent_count=0,
        subagent_type_breakdown={},
        task_count=0,
    )
    detail = {
        "session_id": "session-openclaw",
        "project_path": "openclaw:agent:main",
        "route_slug": "unknown-openclaw-pricing",
        "conversation_ref": "unknown-openclaw-pricing--openclaw-session-openclaw",
        "thread_type": "main",
        "created_at": 1_710_000_600_000,
        "last_updated_at": 1_710_000_660_000,
        "is_running": False,
        "messages": [],
        "plans": [],
        "total_usage": {
            "input_tokens": 50_000,
            "output_tokens": 5_000,
            "cache_creation_tokens": 1_000,
            "cache_read_tokens": 2_000,
        },
        "model": "openclaw-internal-preview",
        "start_time": 1_710_000_600_000,
        "end_time": 1_710_000_660_000,
        "subagents": [],
        "context_analytics": {"buckets": [], "steps": []},
    }

    row = export_pipeline._build_envelope(
        summary=summary,
        detail=export_pipeline.ConversationDetailResponse.model_validate(detail),
        tasks=[],
        source_path="/tmp/openclaw-session.jsonl",
        source_file_modified_at=1_710_000_661_000,
    )

    assert row["summary"]["provider"] == "openclaw"
    assert row["cost"] == {
        "inputCost": pytest.approx(0.0),
        "outputCost": pytest.approx(0.0),
        "cacheWriteCost": pytest.approx(0.0),
        "cacheReadCost": pytest.approx(0.0),
        "totalCost": pytest.approx(0.0),
    }
