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
