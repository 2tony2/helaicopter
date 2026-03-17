from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import uuid

from oats.models import AgentInvocationResult, AgentCommand, PlannedTask


class AgentInvocationError(RuntimeError):
    """Raised when an agent CLI call fails."""


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

    if result.exit_code != 0 and not result.timed_out:
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
    lines.extend(
        [
            "",
            "Return a concise implementation brief with:",
            "1. Likely files or packages involved",
            "2. Ordered implementation steps",
            "3. Main risks or merge-conflict hotspots",
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


def _run_command(
    *,
    command: list[str],
    cwd: Path,
    prompt: str | None,
    timeout_seconds: int,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            input=prompt,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
        return completed, False
    except subprocess.TimeoutExpired as exc:
        return (
            subprocess.CompletedProcess(
                args=command,
                returncode=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
            ),
            True,
        )
