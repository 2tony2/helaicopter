from __future__ import annotations

from pathlib import Path
import re
import subprocess

from oats.models import (
    CommandExecutionRecord,
    ExecutionPlan,
    PlannedTask,
    PullRequestApplyRecord,
    PullRequestPlan,
    RepoConfig,
)
from oats.runner import AgentInvocationError, build_merge_prompt, invoke_agent


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


def build_task_pr_body(task: PlannedTask, integration_branch: str) -> str:
    depends_on = ", ".join(task.depends_on) if task.depends_on else "none"
    lines = [
        f"Overnight Oats task PR for `{task.id}`.",
        "",
        f"- Task: {task.title}",
        f"- Depends on: {depends_on}",
        f"- Merge target: `{integration_branch}`",
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
            task_id=task.id,
            title=build_task_pr_title(task),
            head_branch=task.branch_name,
            base_branch=task.pr_base,
            body=build_task_pr_body(task, plan.integration_branch),
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
