import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from oats.runner import (
    _build_claude_command,
    _build_codex_command,
    _parse_claude_result,
    _parse_codex_result,
    build_planner_prompt,
    build_task_prompt,
)
from oats.models import AgentCommand, PlannedTask


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


def test_codex_command_uses_dangerous_bypass_when_requested() -> None:
    command = _build_codex_command(
        AgentCommand(command="codex", args=["exec"]),
        Path("."),
        "test prompt",
        read_only=False,
        dangerous_bypass=True,
    )

    assert "--dangerously-bypass-approvals-and-sandbox" in command
    assert "--sandbox" not in command


def test_claude_command_uses_bypass_permissions_when_requested() -> None:
    command = _build_claude_command(
        AgentCommand(command="claude", args=[]),
        Path("."),
        requested_session_id="session-123",
        read_only=False,
        dangerous_bypass=True,
    )

    assert "--permission-mode" in command
    assert "bypassPermissions" in command
    assert "--tools" not in command


def test_prompts_switch_out_of_read_only_mode() -> None:
    task = PlannedTask(
        id="task_one",
        title="Task One",
        prompt="Implement a thing.",
        branch_name="codex/oats/task/task-one",
        pr_base="codex/oats/overnight/run",
    )

    planner_prompt = build_planner_prompt("Run: Demo", [task], read_only=False)
    task_prompt = build_task_prompt(task, "Run: Demo", read_only=False)

    assert "Read-only" not in planner_prompt
    assert "Do not modify files" not in task_prompt
    assert "Writable execution run." in task_prompt
    assert "Implement the task now in the current worktree." in task_prompt
