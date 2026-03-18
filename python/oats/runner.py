from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import time
import threading
import uuid
from typing import Any, Callable, TextIO

from oats.models import AgentInvocationResult, AgentCommand, PlannedTask


class AgentInvocationError(RuntimeError):
    """Raised when an agent CLI call fails."""


class _StreamCollector:
    def __init__(
        self,
        stream: TextIO | None,
        *,
        on_line: Callable[[str], None] | None = None,
    ) -> None:
        self._stream = stream
        self._on_line = on_line
        self._chunks: list[str] = []
        self._thread: threading.Thread | None = None
        self.callback_errors: list[Exception] = []

    def start(self) -> None:
        if self._stream is None:
            return
        self._thread = threading.Thread(target=self._collect, daemon=True)
        self._thread.start()

    def _collect(self) -> None:
        if self._stream is None:
            return
        try:
            for line in iter(self._stream.readline, ""):
                self._chunks.append(line)
                if self._on_line is not None:
                    try:
                        self._on_line(line)
                    except Exception as exc:  # pragma: no cover - defensive guard
                        self.callback_errors.append(exc)
        finally:
            self._stream.close()

    def finish(self) -> str:
        if self._thread is not None:
            self._thread.join()
        return "".join(self._chunks)


def invoke_agent(
    *,
    agent_name: str,
    agent_command: AgentCommand,
    role: str,
    cwd: Path,
    prompt: str,
    read_only: bool = True,
    timeout_seconds: int = 20,
    dangerous_bypass: bool = False,
    raise_on_nonzero: bool = True,
    on_heartbeat: Callable[[], None] | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> AgentInvocationResult:
    started_at = datetime.now(timezone.utc)

    if agent_name == "codex":
        command = _build_codex_command(
            agent_command,
            cwd,
            prompt,
            read_only=read_only,
            dangerous_bypass=dangerous_bypass,
        )
        completed, timed_out = _run_command(
            command=command,
            cwd=cwd,
            prompt=None,
            timeout_seconds=timeout_seconds,
            on_heartbeat=on_heartbeat,
            on_stdout_line=(
                (lambda line: _handle_codex_progress_line(line, on_progress))
                if on_progress is not None
                else None
            ),
        )
        result = _parse_codex_result(
            command=command,
            cwd=cwd,
            prompt=prompt,
            role=role,
            completed=completed,
            started_at=started_at,
            timed_out=timed_out,
        )
    elif agent_name == "claude":
        requested_session_id = str(uuid.uuid4())
        command = _build_claude_command(
            agent_command,
            cwd,
            requested_session_id=requested_session_id,
            read_only=read_only,
            dangerous_bypass=dangerous_bypass,
        )
        completed, timed_out = _run_command(
            command=command,
            cwd=cwd,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
            on_heartbeat=on_heartbeat,
            on_stdout_line=(
                (lambda line: _handle_claude_progress_line(line, requested_session_id, on_progress))
                if on_progress is not None
                else None
            ),
        )
        result = _parse_claude_result(
            command=command,
            cwd=cwd,
            prompt=prompt,
            role=role,
            completed=completed,
            started_at=started_at,
            requested_session_id=requested_session_id,
            timed_out=timed_out,
        )
    else:
        raise AgentInvocationError(f"Unsupported agent '{agent_name}'")

    if raise_on_nonzero and result.exit_code != 0 and not result.timed_out:
        raise AgentInvocationError(
            f"{agent_name} {role} invocation failed with exit code {result.exit_code}\n"
            f"stderr:\n{result.raw_stderr or '<empty>'}"
        )
    return result


def build_planner_prompt(
    run_title: str,
    tasks: list[PlannedTask],
    *,
    read_only: bool,
) -> str:
    mode_lines = (
        [
            "Read-only planning run.",
            "Do not modify files, create branches, or run write operations.",
            "Summarize the execution order, dependencies, and likely implementation hotspots for these tasks.",
        ]
        if read_only
        else [
            "Writable planning run.",
            "You may inspect the repo, propose sequencing, and make changes only if they are necessary to unblock execution.",
            "Prefer concrete execution guidance over abstract architecture prose.",
        ]
    )
    lines = [
        *mode_lines,
        f"Run title: {run_title}",
        "",
        "Tasks:",
    ]
    for task in tasks:
        depends_on = ", ".join(task.depends_on) if task.depends_on else "none"
        lines.extend(
            [
                f"- id: {task.id}",
                f"  title: {task.title}",
                f"  depends_on: {depends_on}",
                f"  prompt: {task.prompt}",
            ]
        )
        if task.acceptance_criteria:
            lines.append("  acceptance_criteria:")
            for criterion in task.acceptance_criteria:
                lines.append(f"    - {criterion}")
    lines.extend(
        [
            "",
            "Return a concise execution brief with:",
            "1. Ordered task list",
            "2. Dependency rationale",
            "3. Repo areas likely to change",
        ]
    )
    return "\n".join(lines)


def build_task_prompt(
    task: PlannedTask,
    run_title: str,
    *,
    read_only: bool,
) -> str:
    depends_on = ", ".join(task.depends_on) if task.depends_on else "none"
    mode_lines = (
        [
            "Read-only execution rehearsal.",
            "Do not modify files, create commits, or apply patches.",
        ]
        if read_only
        else [
            "Writable execution run.",
            "You may modify files, run validation commands, and create the implementation needed for this task.",
            "Prefer small, reviewable changes that stay inside the task boundary.",
        ]
    )
    lines = [
        *mode_lines,
        f"Run title: {run_title}",
        f"Task id: {task.id}",
        f"Task title: {task.title}",
        f"Depends on: {depends_on}",
        "",
        "Implementation request:",
        task.prompt,
    ]
    if task.acceptance_criteria:
        lines.extend(["", "Acceptance criteria:"])
        for criterion in task.acceptance_criteria:
            lines.append(f"- {criterion}")
    if task.validation_commands:
        lines.extend(["", "Validation commands:"])
        for command in task.validation_commands:
            lines.append(f"- {command}")
    if read_only:
        lines.extend(
            [
                "",
                "Return a concise implementation brief with:",
                "1. Likely files or packages involved",
                "2. Ordered implementation steps",
                "3. Main risks or merge-conflict hotspots",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Implement the task now in the current worktree.",
                "After making changes, return a concise execution summary with:",
                "1. Files changed",
                "2. Validation commands run and outcomes",
                "3. Remaining risks or follow-ups",
            ]
        )
    return "\n".join(lines)


def build_merge_prompt(
    *,
    task_id: str,
    pr_url: str,
    integration_branch: str,
) -> str:
    return "\n".join(
        [
            "Complete this GitHub pull request merge workflow.",
            "You may use git and gh commands.",
            "Required outcome:",
            f"- Merge PR {pr_url} into {integration_branch} using a merge commit.",
            f"- Keep the source branch for auditability.",
            f"- After merging, fast-forward the local {integration_branch} branch from origin.",
            "",
            "Constraints:",
            f"- Operate only on task {task_id} and the integration branch {integration_branch}.",
            "- Do not create the final PR to main.",
            "- If the PR is already merged, verify the integration branch is up to date locally.",
            "",
            "Return a concise summary of what you did and any issues.",
        ]
    )


def _build_codex_command(
    agent_command: AgentCommand,
    cwd: Path,
    prompt: str,
    *,
    read_only: bool,
    dangerous_bypass: bool,
) -> list[str]:
    command = [agent_command.command, *agent_command.args]
    if "exec" not in agent_command.args:
        command.append("exec")
    command.extend(["-C", str(cwd), "--json"])
    if read_only:
        command.extend(["--sandbox", "read-only"])
    elif dangerous_bypass:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        command.extend(["--sandbox", "workspace-write"])
    command.append(prompt)
    return command


def _build_claude_command(
    agent_command: AgentCommand,
    cwd: Path,
    *,
    requested_session_id: str,
    read_only: bool,
    dangerous_bypass: bool,
) -> list[str]:
    command = [agent_command.command, *agent_command.args]
    command.extend(
        [
            "--print",
            "--output-format",
            "json",
            "--session-id",
            requested_session_id,
            "--add-dir",
            str(cwd),
        ]
    )
    if read_only:
        command.extend(["--tools", ""])
    elif dangerous_bypass:
        command.extend(["--permission-mode", "bypassPermissions"])
    return command


def _parse_codex_result(
    *,
    command: list[str],
    cwd: Path,
    prompt: str,
    role: str,
    completed: subprocess.CompletedProcess[str],
    started_at: datetime,
    timed_out: bool,
) -> AgentInvocationResult:
    thread_id: str | None = None
    output_text = ""

    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        payload_type = payload.get("type")
        if payload_type == "thread.started":
            thread_id = payload.get("thread_id")
        elif payload_type == "item.completed":
            item = payload.get("item", {})
            if item.get("type") == "agent_message":
                output_text = item.get("text", output_text)

    return AgentInvocationResult(
        agent="codex",
        role=role,
        command=command,
        cwd=cwd,
        prompt=prompt,
        session_id=thread_id,
        session_id_field="thread_id" if thread_id else None,
        output_text=output_text,
        raw_stdout=completed.stdout,
        raw_stderr=completed.stderr,
        exit_code=completed.returncode,
        timed_out=timed_out,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
    )


def _handle_codex_progress_line(
    line: str,
    on_progress: Callable[[dict[str, Any]], None] | None,
) -> None:
    if on_progress is None:
        return
    stripped = line.strip()
    if not stripped:
        return
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return
    payload_type = payload.get("type")
    if payload_type == "thread.started":
        thread_id = payload.get("thread_id")
        if isinstance(thread_id, str) and thread_id:
            on_progress(
                {
                    "session_id": thread_id,
                    "session_id_field": "thread_id",
                }
            )
    elif payload_type == "item.completed":
        item = payload.get("item", {})
        if item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str) and text:
                on_progress({"output_text": text})


def _parse_claude_result(
    *,
    command: list[str],
    cwd: Path,
    prompt: str,
    role: str,
    completed: subprocess.CompletedProcess[str],
    started_at: datetime,
    requested_session_id: str,
    timed_out: bool,
) -> AgentInvocationResult:
    session_id: str | None = None
    output_text = ""

    stripped = completed.stdout.strip()
    if stripped:
        try:
            payload = json.loads(stripped)
            session_id = payload.get("session_id")
            output_text = payload.get("result", "")
        except json.JSONDecodeError:
            output_text = stripped
    if not session_id:
        session_id = requested_session_id

    return AgentInvocationResult(
        agent="claude",
        role=role,
        command=command,
        cwd=cwd,
        prompt=prompt,
        session_id=session_id,
        session_id_field="session_id" if session_id else None,
        requested_session_id=requested_session_id,
        output_text=output_text,
        raw_stdout=completed.stdout,
        raw_stderr=completed.stderr,
        exit_code=completed.returncode,
        timed_out=timed_out,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
    )


def _handle_claude_progress_line(
    line: str,
    requested_session_id: str,
    on_progress: Callable[[dict[str, Any]], None] | None,
) -> None:
    if on_progress is None:
        return
    stripped = line.strip()
    if not stripped:
        return
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return
    progress: dict[str, Any] = {"requested_session_id": requested_session_id}
    session_id = payload.get("session_id")
    if isinstance(session_id, str) and session_id:
        progress["session_id"] = session_id
        progress["session_id_field"] = "session_id"
    result = payload.get("result")
    if isinstance(result, str) and result:
        progress["output_text"] = result
    on_progress(progress)


def _run_command(
    *,
    command: list[str],
    cwd: Path,
    prompt: str | None,
    timeout_seconds: int,
    on_heartbeat: Callable[[], None] | None = None,
    on_stdout_line: Callable[[str], None] | None = None,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.PIPE if prompt is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout_collector = _StreamCollector(process.stdout, on_line=on_stdout_line)
    stderr_collector = _StreamCollector(process.stderr)
    stdout_collector.start()
    stderr_collector.start()

    if process.stdin is not None:
        process.stdin.write(prompt)
        process.stdin.close()

    start = time.monotonic()
    next_heartbeat = start

    while True:
        if on_heartbeat is not None:
            now = time.monotonic()
            if now >= next_heartbeat:
                on_heartbeat()
                next_heartbeat = now + 1.0

        return_code = process.poll()
        if return_code is not None:
            process.wait()
            stdout = stdout_collector.finish()
            stderr = stderr_collector.finish()
            return (
                subprocess.CompletedProcess(
                    args=command,
                    returncode=return_code,
                    stdout=stdout,
                    stderr=stderr,
                ),
                False,
            )

        if time.monotonic() - start >= timeout_seconds:
            process.kill()
            process.wait()
            stdout = stdout_collector.finish()
            stderr = stderr_collector.finish()
            return (
                subprocess.CompletedProcess(
                    args=command,
                    returncode=124,
                    stdout=stdout,
                    stderr=stderr,
                ),
                True,
            )

        time.sleep(0.1)
