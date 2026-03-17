import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from oats.runner import _parse_claude_result, _parse_codex_result


def test_parse_codex_result_extracts_thread_id() -> None:
    completed = subprocess.CompletedProcess(
        args=["codex"],
        returncode=0,
        stdout=(
            '{"type":"thread.started","thread_id":"thread-123"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\n'
        ),
        stderr="",
    )

    result = _parse_codex_result(
        command=["codex"],
        cwd=Path("."),
        prompt="test",
        role="planner",
        completed=completed,
        started_at=datetime.now(timezone.utc),
        timed_out=False,
    )

    assert result.session_id == "thread-123"
    assert result.session_id_field == "thread_id"
    assert result.output_text == "done"


def test_parse_claude_result_extracts_session_id() -> None:
    completed = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=json.dumps({"session_id": "session-456", "result": "done"}),
        stderr="",
    )

    result = _parse_claude_result(
        command=["claude"],
        cwd=Path("."),
        prompt="test",
        role="executor",
        completed=completed,
        started_at=datetime.now(timezone.utc),
        requested_session_id="session-456",
        timed_out=False,
    )

    assert result.session_id == "session-456"
    assert result.session_id_field == "session_id"
    assert result.output_text == "done"


def test_parse_claude_result_falls_back_to_requested_session_id() -> None:
    completed = subprocess.CompletedProcess(
        args=["claude"],
        returncode=124,
        stdout="",
        stderr="",
    )

    result = _parse_claude_result(
        command=["claude"],
        cwd=Path("."),
        prompt="test",
        role="executor",
        completed=completed,
        started_at=datetime.now(timezone.utc),
        requested_session_id="requested-789",
        timed_out=True,
    )

    assert result.session_id == "requested-789"
    assert result.timed_out is True
