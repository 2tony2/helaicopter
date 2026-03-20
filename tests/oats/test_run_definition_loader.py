from __future__ import annotations

from pathlib import Path

import pytest

from oats.run_definition_loader import UnsupportedRunDefinitionInputError, load_run_definition


def test_load_run_definition_normalizes_existing_markdown_example() -> None:
    run_definition = load_run_definition(
        Path("examples/prefect_native_oats_orchestration_run.md")
    )

    assert run_definition.title == "Run: Prefect Native Oats Orchestration"
    assert run_definition.source_path == (
        Path.cwd() / "examples" / "prefect_native_oats_orchestration_run.md"
    )
    assert run_definition.config_path == Path.cwd() / ".oats" / "config.toml"
    assert run_definition.repo_root == Path.cwd()
    assert run_definition.default_validation_commands == [
        "npm run lint",
        "uv run --group dev pytest -q",
    ]
    assert run_definition.execution.repo_base_branch == "main"
    assert run_definition.execution.worktree_dir == ".oats-worktrees"
    assert run_definition.execution.default_concurrency == 3

    task = next(task for task in run_definition.tasks if task.task_id == "markdown_run_definition")

    assert task.title == "T003 Markdown-First Canonical Run Definition Layer"
    assert task.depends_on == ["prefect_platform_foundation"]
    assert task.acceptance_criteria == [
        "canonical run-definition models exist",
        "the loader successfully converts current Markdown examples into canonical run definitions",
        "non-Markdown run-definition inputs are explicitly rejected for this rollout",
        "existing parser coverage still passes",
    ]
    assert task.notes == [
        "preserve current Markdown semantics around task titles, dependencies, acceptance criteria, notes, and validation overrides",
        "do not let Prefect-specific fields leak into the canonical input layer",
    ]
    assert task.validation_commands == [
        "uv run --group dev pytest -q tests/oats/test_run_definition_loader.py tests/test_parser.py"
    ]


def test_load_run_definition_uses_repo_validation_defaults_when_no_override() -> None:
    run_definition = load_run_definition(Path("examples/sample_run.md"))

    task = next(task for task in run_definition.tasks if task.task_id == "auth")

    assert task.validation_commands == [
        "npm run lint",
        "uv run --group dev pytest -q",
    ]


def test_load_run_definition_normalizes_full_program_overnight_run() -> None:
    run_definition = load_run_definition(
        Path("examples/full_program_authoritative_analytics_overnight_run.md")
    )

    assert run_definition.title == "Run: Full Program Authoritative Analytics Overnight"
    assert run_definition.source_path == (
        Path.cwd() / "examples" / "full_program_authoritative_analytics_overnight_run.md"
    )

    assert [task.task_id for task in run_definition.tasks] == [
        "semantic_foundation",
        "python_ingestion_foundation",
        "operational_store_migration",
        "warehouse_authority_cutover",
        "orchestration_analytics",
        "frontend_simplification",
        "near_realtime_polish",
        "final_cutover_and_morning_handoff",
    ]

    ingestion = next(task for task in run_definition.tasks if task.task_id == "python_ingestion_foundation")
    frontend = next(task for task in run_definition.tasks if task.task_id == "frontend_simplification")
    final_task = next(
        task for task in run_definition.tasks if task.task_id == "final_cutover_and_morning_handoff"
    )

    assert ingestion.depends_on == ["semantic_foundation"]
    assert frontend.depends_on == ["warehouse_authority_cutover", "orchestration_analytics"]
    assert final_task.depends_on == [
        "frontend_simplification",
        "near_realtime_polish",
        "orchestration_analytics",
    ]
    assert final_task.validation_commands == [
        "uv run --group dev pytest -q tests/oats/test_run_definition_loader.py tests/test_parser.py",
        "uv run oats plan examples/full_program_authoritative_analytics_overnight_run.md",
    ]


def test_load_run_definition_rejects_non_markdown_inputs(tmp_path: Path) -> None:
    invalid_run_spec = tmp_path / "run.yaml"
    invalid_run_spec.write_text("title: invalid\n", encoding="utf-8")

    with pytest.raises(UnsupportedRunDefinitionInputError, match="Markdown"):
        load_run_definition(invalid_run_spec)
