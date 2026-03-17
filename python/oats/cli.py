from __future__ import annotations

from pathlib import Path
import shlex

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from oats.parser import RunSpecParseError, parse_run_spec
from oats.planner import PlanError, build_execution_plan
from oats.repo_config import RepoConfigError, find_repo_config, load_repo_config
from oats.runner import (
    AgentInvocationError,
    build_planner_prompt,
    build_task_prompt,
    invoke_agent,
)
from oats.models import RunExecutionRecord, TaskExecutionRecord
from oats.pr import (
    build_final_pr_plan,
    build_integration_branch_commands,
    build_pr_create_command,
    build_task_pr_plans,
    execute_pr_plan,
)


app = typer.Typer(help="Overnight Oats CLI")
console = Console()


@app.callback()
def callback() -> None:
    """Overnight Oats CLI."""


@app.command()
def plan(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
) -> None:
    """Parse a Markdown run spec and print the resolved plan."""

    search_root = repo.resolve() if repo else run_spec.resolve().parent

    try:
        config_path = find_repo_config(search_root)
        config = load_repo_config(config_path)
        run = parse_run_spec(run_spec.resolve())
        execution_plan = build_execution_plan(
            config=config,
            run_spec=run,
            repo_root=config_path.parent.parent,
            config_path=config_path,
        )
    except (RepoConfigError, RunSpecParseError, PlanError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        Panel.fit(
            f"Run: [bold]{execution_plan.run_title}[/bold]\n"
            f"Repo: {execution_plan.repo_root}\n"
            f"Config: {execution_plan.config_path}\n"
            f"Spec: {execution_plan.run_spec_path}\n"
            f"Integration branch: {execution_plan.integration_branch}\n"
            f"Task PR target: {execution_plan.task_pr_target}\n"
            f"Final PR target: {execution_plan.final_pr_target}",
            title="Execution Plan",
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Task")
    table.add_column("Branch")
    table.add_column("PR Base")
    table.add_column("Depends On")
    table.add_column("Validation")
    table.add_column("Prompt")

    for task in execution_plan.tasks:
        depends_on = ", ".join(task.depends_on) if task.depends_on else "-"
        validation = ", ".join(task.validation_commands) if task.validation_commands else "-"
        table.add_row(
            f"{task.id} ({task.title})",
            task.branch_name,
            task.pr_base,
            depends_on,
            validation,
            task.prompt,
        )

    console.print(table)


@app.command("pr-plan")
def pr_plan(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
) -> None:
    """Print the Git and gh commands for task PRs into the integration branch and the final PR to main."""

    search_root = repo.resolve() if repo else run_spec.resolve().parent

    try:
        config_path = find_repo_config(search_root)
        config = load_repo_config(config_path)
        run = parse_run_spec(run_spec.resolve())
        execution_plan = build_execution_plan(
            config=config,
            run_spec=run,
            repo_root=config_path.parent.parent,
            config_path=config_path,
        )
    except (RepoConfigError, RunSpecParseError, PlanError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        Panel.fit(
            f"Integration branch: {execution_plan.integration_branch}\n"
            f"Task PR target: {execution_plan.task_pr_target}\n"
            f"Final PR target: {execution_plan.final_pr_target}\n"
            f"Auto-merge task PRs: {'yes' if config.git.auto_merge_task_prs_into_integration else 'no'}\n"
            f"Merge operator: {config.agents.merge_operator}",
            title="PR Workflow",
        )
    )

    console.print("[bold]Integration branch setup[/bold]")
    for command in build_integration_branch_commands(execution_plan):
        console.print(shlex.join(command), markup=False)

    task_prs = build_task_pr_plans(execution_plan)
    console.print("\n[bold]Task PR sequence[/bold]")
    for task_pr in task_prs:
        console.print(f"# {task_pr.task_id}")
        console.print(shlex.join(build_pr_create_command(task_pr)), markup=False)
        if config.git.auto_merge_task_prs_into_integration:
            console.print(
                f"{config.agents.merge_operator} will merge {task_pr.head_branch} into {execution_plan.integration_branch}",
                markup=False,
            )

    if config.git.auto_merge_task_prs_into_integration and config.git.auto_create_final_pr:
        final_pr = build_final_pr_plan(execution_plan)
        console.print("\n[bold]Final PR[/bold]")
        console.print(shlex.join(build_pr_create_command(final_pr)), markup=False)
    else:
        console.print("\n[bold]Final PR[/bold]")
        console.print("Skipped until task PRs are merged into the integration branch.", markup=False)


@app.command("pr-apply")
def pr_apply(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
    execute: bool = typer.Option(
        False,
        "--execute/--dry-run",
        help="Run git and gh commands instead of only recording them.",
    ),
) -> None:
    """Apply the PR workflow: create task PRs into the integration branch, merge them, then create the final PR."""

    search_root = repo.resolve() if repo else run_spec.resolve().parent

    try:
        config_path = find_repo_config(search_root)
        config = load_repo_config(config_path)
        run = parse_run_spec(run_spec.resolve())
        execution_plan = build_execution_plan(
            config=config,
            run_spec=run,
            repo_root=config_path.parent.parent,
            config_path=config_path,
        )
        apply_record = execute_pr_plan(
            execution_plan,
            config,
            execute=execute,
        )
    except (RepoConfigError, RunSpecParseError, PlanError, RuntimeError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    runs_dir = execution_plan.repo_root / ".oats" / "pr-runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    record_name = f"{execution_plan.run_spec_path.stem}-{apply_record.recorded_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    record_path = runs_dir / record_name
    apply_record.record_path = record_path
    record_path.write_text(apply_record.model_dump_json(indent=2))

    console.print(
        Panel.fit(
            f"Run: [bold]{apply_record.run_title}[/bold]\n"
            f"Repo: {apply_record.repo_root}\n"
            f"Integration branch: {apply_record.integration_branch}\n"
            f"Final PR target: {apply_record.final_pr_target}\n"
            f"Auto-merge task PRs: {'yes' if apply_record.auto_merge_enabled else 'no'}\n"
            f"Final PR created: {'yes' if apply_record.final_pr_created else 'no'}\n"
            f"Mode: {'execute' if apply_record.executed else 'dry-run'}\n"
            f"Record: {apply_record.record_path}",
            title="PR Apply",
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Label")
    table.add_column("Executed")
    table.add_column("Exit")
    table.add_column("Agent")
    table.add_column("Session")
    table.add_column("Command")

    for command_record in apply_record.commands:
        table.add_row(
            command_record.label,
            "yes" if command_record.executed else "no",
            str(command_record.exit_code),
            command_record.agent or "-",
            command_record.session_id or "-",
            shlex.join(command_record.command),
        )

    console.print(table)


@app.command()
def run(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
    read_only: bool = typer.Option(
        True,
        "--read-only/--allow-writes",
        help="Invoke agents in non-destructive mode.",
    ),
    timeout_seconds: int = typer.Option(
        20,
        "--timeout-seconds",
        min=1,
        help="Maximum time to wait for each provider call before returning partial session metadata.",
    ),
    dangerous_bypass: bool = typer.Option(
        False,
        "--dangerous-bypass",
        help="When writes are allowed, invoke Codex/Claude with permission-bypass flags.",
    ),
) -> None:
    """Execute a minimal agent run and persist provider session metadata."""

    search_root = repo.resolve() if repo else run_spec.resolve().parent

    try:
        config_path = find_repo_config(search_root)
        config = load_repo_config(config_path)
        run_model = parse_run_spec(run_spec.resolve())
        execution_plan = build_execution_plan(
            config=config,
            run_spec=run_model,
            repo_root=config_path.parent.parent,
            config_path=config_path,
        )
    except (RepoConfigError, RunSpecParseError, PlanError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    try:
        planner_result = invoke_agent(
            agent_name=config.agents.planner,
            agent_command=config.agent[config.agents.planner],
            role="planner",
            cwd=execution_plan.repo_root,
            prompt=build_planner_prompt(
                execution_plan.run_title,
                execution_plan.tasks,
                read_only=read_only,
            ),
            read_only=read_only,
            timeout_seconds=timeout_seconds,
            dangerous_bypass=dangerous_bypass,
        )

        task_records: list[TaskExecutionRecord] = []
        for task in execution_plan.tasks:
            invocation = invoke_agent(
                agent_name=config.agents.executor,
                agent_command=config.agent[config.agents.executor],
                role="executor",
                cwd=execution_plan.repo_root,
                prompt=build_task_prompt(
                    task,
                    execution_plan.run_title,
                    read_only=read_only,
                ),
                read_only=read_only,
                timeout_seconds=timeout_seconds,
                dangerous_bypass=dangerous_bypass,
            )
            task_records.append(
                TaskExecutionRecord(
                    task_id=task.id,
                    title=task.title,
                    depends_on=task.depends_on,
                    invocation=invocation,
                )
            )
    except AgentInvocationError as exc:
        console.print(f"[red]Execution error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    record = RunExecutionRecord(
        run_title=execution_plan.run_title,
        repo_root=execution_plan.repo_root,
        config_path=execution_plan.config_path,
        run_spec_path=execution_plan.run_spec_path,
        mode="read-only" if read_only else "writable",
        planner=planner_result,
        integration_branch=execution_plan.integration_branch,
        task_pr_target=execution_plan.task_pr_target,
        final_pr_target=execution_plan.final_pr_target,
        tasks=task_records,
    )

    runs_dir = execution_plan.repo_root / ".oats" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    record_name = f"{execution_plan.run_spec_path.stem}-{record.recorded_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    record_path = runs_dir / record_name
    record.record_path = record_path
    record_path.write_text(record.model_dump_json(indent=2))

    console.print(
        Panel.fit(
            f"Run: [bold]{record.run_title}[/bold]\n"
            f"Repo: {record.repo_root}\n"
            f"Integration branch: {record.integration_branch}\n"
            f"Task PR target: {record.task_pr_target}\n"
            f"Final PR target: {record.final_pr_target}\n"
            f"Record: {record.record_path}",
            title="Execution Record",
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Role")
    table.add_column("Agent")
    table.add_column("Session Field")
    table.add_column("Session ID")
    table.add_column("Exit")
    table.add_column("Timed Out")

    if record.planner:
        table.add_row(
            "planner",
            record.planner.agent,
            record.planner.session_id_field or "-",
            record.planner.session_id or "-",
            str(record.planner.exit_code),
            "yes" if record.planner.timed_out else "no",
        )
    for task in record.tasks:
        table.add_row(
            f"executor:{task.task_id}",
            task.invocation.agent,
            task.invocation.session_id_field or "-",
            task.invocation.session_id or "-",
            str(task.invocation.exit_code),
            "yes" if task.invocation.timed_out else "no",
        )

    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
