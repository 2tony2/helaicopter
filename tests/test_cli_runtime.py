from datetime import datetime, timezone
from pathlib import Path

from oats.cli import _execute_run, _prepare_retryable_tasks
from oats.models import AgentInvocationResult
from oats.parser import parse_run_spec
from oats.planner import build_execution_plan
from oats.repo_config import find_repo_config, load_repo_config


def test_execute_run_skips_planner_when_requested(monkeypatch) -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run = parse_run_spec(Path("examples/sample_run.md"))
    execution_plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    calls: list[str] = []

    def fake_invoke_agent(**kwargs):
        calls.append(kwargs["role"])
        return AgentInvocationResult(
            agent=kwargs["agent_name"],
            role=kwargs["role"],
            command=[kwargs["agent_name"]],
            cwd=kwargs["cwd"],
            prompt=kwargs["prompt"],
            exit_code=0,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("oats.cli.invoke_agent", fake_invoke_agent)

    record, state = _execute_run(
        config=config,
        execution_plan=execution_plan,
        read_only=True,
        timeout_seconds=1,
        dangerous_bypass=False,
        skip_planner=True,
    )

    assert "planner" not in calls
    assert all(call == "executor" for call in calls)
    assert state.planner is None
    assert record.tasks


def test_execute_run_retries_transient_task_failure(monkeypatch) -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    config.agents.executor = "codex"
    config.execution.max_task_attempts = 2
    config.execution.retry_backoff_seconds = 0
    run = parse_run_spec(Path("examples/sample_run.md"))
    execution_plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    calls: list[str] = []
    failures = {"auth": 0}

    def fake_invoke_agent(**kwargs):
        prompt = kwargs["prompt"]
        task_id = "auth" if "Task id: auth" in prompt else "dashboard_api"
        calls.append(task_id)
        if task_id == "auth" and failures["auth"] == 0:
            failures["auth"] += 1
            return AgentInvocationResult(
                agent=kwargs["agent_name"],
                role=kwargs["role"],
                command=[kwargs["agent_name"]],
                cwd=kwargs["cwd"],
                prompt=prompt,
                exit_code=1,
                output_text='API Error: 500 {"type":"error","error":{"type":"api_error","message":"Internal server error"}}',
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
        return AgentInvocationResult(
            agent=kwargs["agent_name"],
            role=kwargs["role"],
            command=[kwargs["agent_name"]],
            cwd=kwargs["cwd"],
            prompt=prompt,
            exit_code=0,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("oats.cli.invoke_agent", fake_invoke_agent)

    record, state = _execute_run(
        config=config,
        execution_plan=execution_plan,
        read_only=True,
        timeout_seconds=1,
        dangerous_bypass=False,
        skip_planner=True,
    )

    auth_task = next(task for task in state.tasks if task.task_id == "auth")
    assert auth_task.status == "succeeded"
    assert auth_task.attempts == 2
    assert calls[:2] == ["auth", "auth"]
    assert record.tasks


def test_prepare_retryable_tasks_resets_failed_work() -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run = parse_run_spec(Path("examples/sample_run.md"))
    execution_plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    _, state = _execute_run(
        config=config,
        execution_plan=execution_plan,
        read_only=True,
        timeout_seconds=1,
        dangerous_bypass=False,
        skip_planner=True,
    )
    task = next(item for item in state.tasks if item.task_id == "auth")
    task.status = "failed"
    state.status = "failed"

    changed = _prepare_retryable_tasks(state)

    assert changed is True
    assert task.status == "pending"
    assert task.attempts == 0
    assert state.status == "pending"


def test_prepare_retryable_tasks_resets_exhausted_pending_work() -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run = parse_run_spec(Path("examples/sample_run.md"))
    execution_plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    _, state = _execute_run(
        config=config,
        execution_plan=execution_plan,
        read_only=True,
        timeout_seconds=1,
        dangerous_bypass=False,
        skip_planner=True,
    )
    task = next(item for item in state.tasks if item.task_id == "auth")
    task.status = "pending"
    task.attempts = 2
    state.status = "running"

    changed = _prepare_retryable_tasks(state)

    assert changed is True
    assert task.status == "pending"
    assert task.attempts == 0
    assert state.status == "pending"


def test_execute_run_revisits_blocked_tasks_when_dependencies_finish(monkeypatch) -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run = parse_run_spec(Path("examples/sample_run.md"))
    execution_plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )
    execution_plan.tasks = list(reversed(execution_plan.tasks))

    calls: list[str] = []

    def fake_invoke_agent(**kwargs):
        prompt = kwargs["prompt"]
        task_id = "dashboard_api" if "Task id: dashboard_api" in prompt else "auth"
        calls.append(task_id)
        return AgentInvocationResult(
            agent=kwargs["agent_name"],
            role=kwargs["role"],
            command=[kwargs["agent_name"]],
            cwd=kwargs["cwd"],
            prompt=prompt,
            exit_code=0,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("oats.cli.invoke_agent", fake_invoke_agent)

    _, state = _execute_run(
        config=config,
        execution_plan=execution_plan,
        read_only=True,
        timeout_seconds=1,
        dangerous_bypass=False,
        skip_planner=True,
    )

    auth_task = next(task for task in state.tasks if task.task_id == "auth")
    dashboard_task = next(task for task in state.tasks if task.task_id == "dashboard_api")
    assert auth_task.status == "succeeded"
    assert dashboard_task.status == "succeeded"
    assert calls == ["auth", "dashboard_api"]
    assert state.status == "completed"
