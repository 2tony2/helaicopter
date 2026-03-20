from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess

from helaicopter_domain.ids import TaskId
from oats.models import (
    CommandExecutionRecord,
    ExecutionPlan,
    FinalPullRequestSnapshot,
    OperationHistoryEntry,
    PlannedTask,
    PullRequestApplyRecord,
    PullRequestPlan,
    RepoConfig,
    RunRuntimeState,
    TaskPullRequestSnapshot,
    TaskRuntimeRecord,
)
from oats.runner import AgentInvocationError, build_merge_prompt, invoke_agent
from oats.runtime_state import resolve_runtime_state, write_runtime_state


class PullRequestMergeConflictError(RuntimeError):
    """Raised when GitHub reports that a PR cannot be merged cleanly."""


def slugify_branch_component(value: str, *, fallback: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    compact_slug = "-".join(segment for segment in slug.split("-") if segment)
    return compact_slug or fallback


def build_task_branch_name(prefix: str, task_id: str) -> str:
    normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    return f"{normalized_prefix}{slugify_branch_component(task_id, fallback='task')}"


def build_integration_branch_name(prefix: str, run_title: str) -> str:
    normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    return f"{normalized_prefix}{slugify_branch_component(run_title, fallback='run')}"


def build_final_pr_title(run_title: str) -> str:
    return f"[oats] {run_title}"


def build_task_pr_title(task: PlannedTask) -> str:
    return f"[oats][{task.id}] {task.title}"


def build_task_pr_body(task: PlannedTask) -> str:
    depends_on = ", ".join(task.depends_on) if task.depends_on else "none"
    lines = [
        f"Overnight Oats task PR for `{task.id}`.",
        "",
        f"- Task: {task.title}",
        f"- Depends on: {depends_on}",
        f"- Merge target: `{task.pr_base}`",
    ]
    if task.acceptance_criteria:
        lines.extend(["", "Acceptance criteria:"])
        for criterion in task.acceptance_criteria:
            lines.append(f"- {criterion}")
    return "\n".join(lines)


def build_final_pr_body(plan: ExecutionPlan) -> str:
    lines = [
        f"Final Overnight Oats review PR for `{plan.run_title}`.",
        "",
        f"- Integration branch: `{plan.integration_branch}`",
        f"- Base branch: `{plan.final_pr_target}`",
        "",
        "Merged task PRs:",
    ]
    for task in plan.tasks:
        lines.append(f"- `{task.id}` from `{task.branch_name}`")
    return "\n".join(lines)


def build_task_pr_plans(plan: ExecutionPlan) -> list[PullRequestPlan]:
    return [
        PullRequestPlan(
            role="task",
            task_id=TaskId(task.id),
            title=build_task_pr_title(task),
            head_branch=task.branch_name,
            base_branch=task.pr_base,
            body=build_task_pr_body(task),
        )
        for task in plan.tasks
    ]


def build_final_pr_plan(plan: ExecutionPlan) -> PullRequestPlan:
    return PullRequestPlan(
        role="final",
        title=plan.final_pr_title,
        head_branch=plan.integration_branch,
        base_branch=plan.final_pr_target,
        body=build_final_pr_body(plan),
    )


def build_integration_branch_commands(plan: ExecutionPlan) -> list[list[str]]:
    return [
        ["git", "fetch", "origin", plan.integration_branch_base],
        [
            "git",
            "checkout",
            "-B",
            plan.integration_branch,
            f"origin/{plan.integration_branch_base}",
        ],
        ["git", "push", "-u", "origin", plan.integration_branch],
    ]


def build_pr_create_command(pr_plan: PullRequestPlan) -> list[str]:
    command = [
        "gh",
        "pr",
        "create",
        "--base",
        pr_plan.base_branch,
        "--head",
        pr_plan.head_branch,
        "--title",
        pr_plan.title,
        "--body",
        pr_plan.body,
    ]
    if pr_plan.draft:
        command.append("--draft")
    return command


def execute_pr_plan(
    plan: ExecutionPlan,
    config: RepoConfig,
    *,
    execute: bool,
    timeout_seconds: int = 120,
) -> PullRequestApplyRecord:
    commands: list[CommandExecutionRecord] = []
    final_pr_created = False

    for index, command in enumerate(build_integration_branch_commands(plan), start=1):
        commands.append(
            _run_command(
                label=f"integration-{index}",
                command=command,
                cwd=plan.repo_root,
                execute=execute,
            )
        )
        _raise_for_failure(commands[-1])

    for task_pr in build_task_pr_plans(plan):
        create_record = _run_command(
            label=f"task-pr-create:{task_pr.task_id}",
            command=build_pr_create_command(task_pr),
            cwd=plan.repo_root,
            execute=execute,
        )
        commands.append(create_record)
        _raise_for_failure(create_record)

        if config.git.auto_merge_task_prs_into_integration:
            pr_url = (
                _parse_pr_url(create_record.stdout)
                if execute
                else f"https://github.com/example/example/pull/{task_pr.task_id}"
            )
            merge_record = _run_merge_agent(
                task_id=task_pr.task_id or task_pr.head_branch,
                pr_url=pr_url,
                plan=plan,
                config=config,
                execute=execute,
                timeout_seconds=timeout_seconds,
            )
            commands.append(merge_record)
            _raise_for_failure(merge_record)

    if config.git.auto_merge_task_prs_into_integration and config.git.auto_create_final_pr:
        final_pr = build_final_pr_plan(plan)
        final_record = _run_command(
            label="final-pr-create",
            command=build_pr_create_command(final_pr),
            cwd=plan.repo_root,
            execute=execute,
        )
        commands.append(final_record)
        _raise_for_failure(final_record)
        final_pr_created = True

    return PullRequestApplyRecord(
        run_title=plan.run_title,
        repo_root=plan.repo_root,
        config_path=plan.config_path,
        run_spec_path=plan.run_spec_path,
        integration_branch=plan.integration_branch,
        final_pr_target=plan.final_pr_target,
        auto_merge_enabled=config.git.auto_merge_task_prs_into_integration,
        final_pr_created=final_pr_created,
        executed=execute,
        commands=commands,
    )


def _run_command(
    *,
    label: str,
    command: list[str],
    cwd: Path,
    execute: bool,
) -> CommandExecutionRecord:
    if not execute:
        return CommandExecutionRecord(
            label=label,
            command=command,
            cwd=cwd,
            executed=False,
        )

    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandExecutionRecord(
        label=label,
        command=command,
        cwd=cwd,
        executed=True,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _raise_for_failure(record: CommandExecutionRecord) -> None:
    if record.exit_code != 0:
        raise RuntimeError(
            f"Command failed for {record.label} with exit code {record.exit_code}"
        )


def _parse_pr_url(stdout: str) -> str:
    match = re.search(r"https://github\.com/\S+/pull/\d+", stdout)
    if not match:
        raise RuntimeError("Could not parse PR URL from gh pr create output")
    return match.group(0)


def _run_merge_agent(
    *,
    task_id: str,
    pr_url: str,
    plan: ExecutionPlan,
    config: RepoConfig,
    execute: bool,
    timeout_seconds: int,
) -> CommandExecutionRecord:
    prompt = build_merge_prompt(
        task_id=task_id,
        pr_url=pr_url,
        integration_branch=plan.integration_branch,
    )
    agent_name = config.agents.merge_operator
    agent_command = config.agent[agent_name]

    if not execute:
        return CommandExecutionRecord(
            label=f"task-pr-merge:{task_id}",
            command=[agent_name, "merge", pr_url, "->", plan.integration_branch],
            cwd=plan.repo_root,
            executed=False,
            agent=agent_name,
        )

    try:
        invocation = invoke_agent(
            agent_name=agent_name,
            agent_command=agent_command,
            role="merge_operator",
            cwd=plan.repo_root,
            prompt=prompt,
            read_only=False,
            timeout_seconds=timeout_seconds,
            dangerous_bypass=True,
        )
    except AgentInvocationError as exc:
        raise RuntimeError(str(exc)) from exc

    return CommandExecutionRecord(
        label=f"task-pr-merge:{task_id}",
        command=invocation.command,
        cwd=plan.repo_root,
        executed=True,
        exit_code=invocation.exit_code,
        stdout=invocation.raw_stdout,
        stderr=invocation.raw_stderr,
        agent=invocation.agent,
        session_id=invocation.session_id,
        session_id_field=invocation.session_id_field,
        timed_out=invocation.timed_out,
    )


def refresh_run(
    state: RunRuntimeState,
    github_client,
    *,
    action: str = "refresh",
) -> RunRuntimeState:
    started_at = datetime.now(timezone.utc)
    state.active_operation = OperationHistoryEntry(kind=_action_kind(action), status="started")
    for task in state.tasks:
        if task.task_pr.state == "not_created":
            continue

        task.task_pr = _stamp_task_snapshot(github_client.read_task_pr(task))
        if task.task_pr.state == "merged":
            _retarget_child_prs(state, task, github_client)
            continue
        if not _merge_policy_allows(task.task_pr):
            continue

        try:
            task.task_pr = _stamp_task_snapshot(
                github_client.merge_task_pr(task, task.task_pr, merge_method="merge_commit")
            )
        except PullRequestMergeConflictError as exc:
            conflict_entry = OperationHistoryEntry(
                kind="conflict_resolution",
                status="started",
                details={"task_id": str(task.task_id), "error": str(exc)},
            )
            task.operation_history.append(conflict_entry)
            state.active_operation = conflict_entry
            state.stack_status = "resolving_conflict"
            state.operation_history.append(
                OperationHistoryEntry(
                    kind=_action_kind(action),
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    details={"task_id": str(task.task_id)},
                )
            )
            write_runtime_state(state)
            return state

        task.status = "succeeded"
        task.operation_history.append(
            OperationHistoryEntry(
                kind="pr_merge",
                status="succeeded",
                finished_at=datetime.now(timezone.utc),
                details={"task_id": str(task.task_id)},
            )
        )
        _retarget_child_prs(state, task, github_client)

    if _should_create_final_pr(state):
        state.final_pr = _stamp_final_snapshot(github_client.create_final_pr(state))
        state.operation_history.append(
            OperationHistoryEntry(
                kind="pr_create",
                status="succeeded",
                finished_at=datetime.now(timezone.utc),
                details={"role": "final"},
            )
        )

    state.final_pr = _stamp_final_snapshot(github_client.read_final_pr(state))
    state.stack_status = _derive_stack_status(state)
    if state.final_pr.state == "merged":
        state.status = "completed"
        state.stack_status = "completed"

    state.operation_history.append(
        OperationHistoryEntry(
            kind=_action_kind(action),
            status="succeeded",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )
    )
    state.active_operation = None
    write_runtime_state(state)
    return state


def resume_run(
    run_id: str,
    repo_root: Path,
    github_client,
) -> RunRuntimeState:
    state = resolve_runtime_state(repo_root, run_id=run_id)
    refreshed = refresh_run(state=state, github_client=github_client, action="resume")
    tasks_by_id = {str(task.task_id): task for task in refreshed.tasks}
    for task in refreshed.tasks:
        if task.status != "blocked":
            continue
        if not all(
            tasks_by_id[dependency].task_pr.state == "merged" for dependency in task.depends_on
        ):
            continue
        task.status = "pending"
        task.parent_branch = refreshed.feature_branch.name
        task.pr_base = refreshed.feature_branch.name
    write_runtime_state(refreshed)
    return refreshed


def _retarget_child_prs(
    state: RunRuntimeState,
    merged_task: TaskRuntimeRecord,
    github_client,
) -> None:
    for child in state.tasks:
        if str(merged_task.task_id) not in child.depends_on:
            continue
        if child.task_pr.state != "open":
            continue
        if child.task_pr.base_branch != merged_task.branch_name:
            continue
        child.task_pr = _stamp_task_snapshot(
            github_client.retarget_task_pr(child, base_branch=state.feature_branch.name)
        )
        merged_task.operation_history.append(
            OperationHistoryEntry(
                kind="pr_retarget",
                status="succeeded",
                finished_at=datetime.now(timezone.utc),
                details={"child_task_id": str(child.task_id)},
            )
        )


def _merge_policy_allows(snapshot: TaskPullRequestSnapshot) -> bool:
    if snapshot.state != "open":
        return False
    if snapshot.review_summary.blocking_state == "changes_requested":
        return False
    if snapshot.merge_gate_status == "merge_ready":
        return True
    checks_state = str(snapshot.checks_summary.get("state", "")).lower()
    return snapshot.merge_gate_status == "awaiting_checks" and checks_state == "success"


def _should_create_final_pr(state: RunRuntimeState) -> bool:
    return (
        state.final_pr.state == "not_created"
        and state.tasks
        and all(task.task_pr.state == "merged" for task in state.tasks)
    )


def _derive_stack_status(
    state: RunRuntimeState,
) -> str:
    if state.final_pr.state == "merged":
        return "completed"
    if state.final_pr.state in {"open", "ready_for_review"}:
        return "ready_for_final_review"
    if any(task.task_pr.state == "open" for task in state.tasks):
        return "awaiting_task_merge"
    return "building"


def _stamp_task_snapshot(snapshot: TaskPullRequestSnapshot) -> TaskPullRequestSnapshot:
    updates: dict[str, object] = {
        "last_refreshed_at": snapshot.last_refreshed_at or datetime.now(timezone.utc),
    }
    if snapshot.state == "merged":
        updates["merge_gate_status"] = "merged"
    return snapshot.model_copy(update=updates, deep=True)


def _stamp_final_snapshot(snapshot: FinalPullRequestSnapshot) -> FinalPullRequestSnapshot:
    updates: dict[str, object] = {
        "last_refreshed_at": snapshot.last_refreshed_at or datetime.now(timezone.utc),
    }
    if snapshot.state == "merged":
        updates["review_gate_status"] = "merged"
    return snapshot.model_copy(update=updates, deep=True)


def _action_kind(action: str) -> str:
    return "resume" if action == "resume" else "refresh"
