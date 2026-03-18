from pathlib import Path
import threading

from oats.models import AgentInvocationResult
from oats.runtime_state import (
    append_progress_event,
    apply_agent_result,
    build_initial_runtime_state,
    build_plan_snapshot,
    load_runtime_state,
    prepare_invocation_runtime,
    write_plan_snapshot,
    write_runtime_state,
)
from oats.planner import build_execution_plan
from oats.parser import parse_run_spec
from oats.repo_config import find_repo_config, load_repo_config


def test_runtime_state_round_trip_persists_plan_and_state(tmp_path: Path) -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run = parse_run_spec(Path("examples/sample_run.md"))
    execution_plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=tmp_path,
        config_path=tmp_path / ".oats" / "config.toml",
    )

    state = build_initial_runtime_state(
        execution_plan,
        mode="writable",
        run_id="sample-run-1",
        executor_agent=config.agents.executor,
    )
    plan_path = write_plan_snapshot(build_plan_snapshot(state, execution_plan), state.runtime_dir)
    state_path = write_runtime_state(state)
    append_progress_event(state, event_type="run_started")

    loaded = load_runtime_state(state_path)

    assert plan_path.exists()
    assert loaded.run_id == "sample-run-1"
    assert loaded.mode == "writable"
    assert loaded.tasks[0].agent == config.agents.executor
    assert (state.runtime_dir / "events.jsonl").exists()


def test_apply_agent_result_updates_runtime_invocation() -> None:
    invocation = prepare_invocation_runtime(
        agent="codex",
        role="executor",
        cwd=Path("."),
        prompt="do the thing",
    )

    result = AgentInvocationResult(
        agent="codex",
        role="executor",
        command=["codex", "exec"],
        cwd=Path("."),
        prompt="do the thing",
        session_id="thread-123",
        session_id_field="thread_id",
        output_text="done",
        raw_stdout="{}",
        raw_stderr="",
        exit_code=0,
    )

    updated = apply_agent_result(invocation, result)

    assert updated.session_id == "thread-123"
    assert updated.exit_code == 0
    assert updated.finished_at is not None


def test_write_runtime_state_tolerates_concurrent_writes(tmp_path: Path) -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run = parse_run_spec(Path("examples/sample_run.md"))
    execution_plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=tmp_path,
        config_path=tmp_path / ".oats" / "config.toml",
    )
    state = build_initial_runtime_state(
        execution_plan,
        mode="writable",
        run_id="sample-run-concurrent",
        executor_agent=config.agents.executor,
    )

    errors: list[Exception] = []

    def writer() -> None:
        try:
            for _ in range(20):
                write_runtime_state(state)
        except Exception as exc:  # pragma: no cover - test failure path
            errors.append(exc)

    threads = [threading.Thread(target=writer) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert (state.runtime_dir / "state.json").exists()
