from pathlib import Path

from oats.parser import parse_run_spec


def test_parse_run_spec_extracts_tasks() -> None:
    run = parse_run_spec(Path("examples/sample_run.md"))

    assert run.title == "Run: Auth And Dashboard"
    assert [task.id for task in run.tasks] == ["auth", "dashboard_api"]
    assert run.tasks[1].depends_on == ["auth"]
    assert run.tasks[0].acceptance_criteria == [
        "signup endpoint exists",
        "login returns JWT",
        "auth middleware protects private routes",
    ]


def test_parse_run_spec_extracts_task_execution_overrides(tmp_path: Path) -> None:
    run_spec = tmp_path / "overrides.md"
    run_spec.write_text(
        """# Run: Overrides

## Tasks

### api
Title: API work
Agent: claude
Model: claude-sonnet-4-5
Reasoning effort: high

Implement the API.
""",
        encoding="utf-8",
    )

    run = parse_run_spec(run_spec)

    assert run.tasks[0].agent == "claude"
    assert run.tasks[0].model == "claude-sonnet-4-5"
    assert run.tasks[0].reasoning_effort == "high"
