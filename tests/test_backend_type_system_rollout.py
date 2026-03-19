from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Annotated, get_args, get_origin, get_type_hints

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
BASELINE_DOC = ROOT / "docs" / "python-backend-type-system-baseline.md"
BASELINE_JSON = ROOT / "docs" / "superpowers" / "baselines" / "2026-03-18-python-backend-pyright-baseline.json"
WORKFLOW = ROOT / ".github" / "workflows" / "backend-quality.yml"
ROLLOUT_DOC = ROOT / "docs" / "fastapi-backend-rollout.md"

EXPECTED_DEV_DEPENDENCIES = {"httpx", "pyright", "pytest", "pytest-cov", "ruff"}
EXPECTED_PYRIGHT_INCLUDE = [
    "python/helaicopter_api/server",
    "python/helaicopter_api/schema",
    "python/helaicopter_api/ports",
    "python/oats/models.py",
]
TARGETED_CAMEL_SCHEMA_PATHS = {
    "python/helaicopter_api/schema/database.py",
    "python/helaicopter_api/schema/evaluations.py",
    "python/helaicopter_api/schema/orchestration.py",
    "python/helaicopter_api/schema/subscriptions.py",
}
DEFERRED_LEGACY_SCHEMA_PATHS = {
    "python/helaicopter_api/schema/analytics.py",
    "python/helaicopter_api/schema/conversations.py",
}
EXPECTED_PUBLIC_RAW_DICT_COUNTS: dict[str, int] = {}


def _load_pyproject() -> dict[str, object]:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def _package_names(specs: list[str]) -> set[str]:
    names: set[str] = set()
    for spec in specs:
        match = re.match(r"[A-Za-z0-9_-]+", spec)
        assert match is not None
        names.add(match.group(0))
    return names


def _type_hints(target: object) -> dict[str, object]:
    return get_type_hints(target, include_extras=True)


def test_pyproject_commits_backend_tooling_baseline() -> None:
    pyproject = _load_pyproject()

    dev_group = pyproject["dependency-groups"]["dev"]
    assert EXPECTED_DEV_DEPENDENCIES.issubset(_package_names(dev_group))

    pyright = pyproject["tool"]["pyright"]
    assert pyright["pythonVersion"] == "3.13"
    assert pyright["typeCheckingMode"] == "strict"
    assert pyright["include"] == EXPECTED_PYRIGHT_INCLUDE

    ruff = pyproject["tool"]["ruff"]
    assert ruff["target-version"] == "py313"
    assert ruff["src"] == ["python", "tests"]


def test_baseline_docs_capture_scope_and_initial_pyright_results() -> None:
    assert BASELINE_DOC.exists()
    assert BASELINE_JSON.exists()

    content = BASELINE_DOC.read_text(encoding="utf-8")
    for path in EXPECTED_PYRIGHT_INCLUDE:
        assert path in content

    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    assert baseline["summary"]["errorCount"] > 0
    assert f"{baseline['summary']['errorCount']} errors" in content


def test_backend_quality_workflow_requires_pyright_for_the_scoped_backend_surface() -> None:
    assert WORKFLOW.exists()

    content = WORKFLOW.read_text(encoding="utf-8")
    assert "uv run --group dev ruff check python tests" in content
    assert "uv run --group dev pytest -q" in content
    assert "uv run --group dev pyright" in content
    assert "continue-on-error: true" not in content


def test_wave_zero_guardrails_freeze_alias_helpers_and_public_raw_dict_seams() -> None:
    alias_hits = {
        str(path.relative_to(ROOT))
        for path in (ROOT / "python" / "helaicopter_api" / "schema").rglob("*.py")
        if "def _to_camel(" in path.read_text(encoding="utf-8")
    }
    assert alias_hits == set()

    common_content = (ROOT / "python" / "helaicopter_api" / "schema" / "common.py").read_text(
        encoding="utf-8"
    )
    assert "def to_camel(" in common_content
    assert "def camel_case_request_config(" in common_content
    assert "class CamelCaseHttpResponseModel(BaseModel):" in common_content

    for relative_path in TARGETED_CAMEL_SCHEMA_PATHS:
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "populate_by_name=True" not in content

    for relative_path in DEFERRED_LEGACY_SCHEMA_PATHS:
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "legacy `snake_case`" in content
        assert "deferred" in content

    raw_dict_counts: dict[str, int] = {}
    for relative_path in EXPECTED_PUBLIC_RAW_DICT_COUNTS:
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        raw_dict_counts[relative_path] = content.count("dict[str, Any]")

    assert raw_dict_counts == EXPECTED_PUBLIC_RAW_DICT_COUNTS

    boundary_hits: dict[str, int] = {}
    for path in sorted((ROOT / "python" / "helaicopter_api" / "schema").rglob("*.py")):
        relative_path = str(path.relative_to(ROOT))
        count = path.read_text(encoding="utf-8").count("dict[str, Any]")
        if count:
            boundary_hits[relative_path] = count
    for path in sorted((ROOT / "python" / "helaicopter_api" / "ports").rglob("*.py")):
        relative_path = str(path.relative_to(ROOT))
        count = path.read_text(encoding="utf-8").count("dict[str, Any]")
        if count:
            boundary_hits[relative_path] = count

    assert boundary_hits == EXPECTED_PUBLIC_RAW_DICT_COUNTS


def test_wave_two_domain_catalog_centralizes_high_value_vocabularies() -> None:
    from helaicopter_api.ports.app_sqlite import ConversationEvaluationRecord
    from helaicopter_api.ports.evaluations import EvaluationJobRequest, EvaluationJobResult
    from helaicopter_api.schema.database import DatabaseRuntimeResponse, DatabaseStatusResponse
    from helaicopter_api.schema.evaluations import (
        ConversationEvaluationCreateRequest,
        ConversationEvaluationResponse,
    )
    from helaicopter_api.schema.orchestration import (
        OrchestrationRunResponse,
        OrchestrationTaskResponse,
    )
    from helaicopter_domain.ids import RunId, TaskId
    from helaicopter_domain.vocab import (
        DatabaseRefreshStatus,
        EvaluationScope,
        EvaluationStatus,
        ProviderName,
        ProviderSelection,
        RunRuntimeStatus,
        RuntimeReadBackend,
        TaskRuntimeStatus,
    )
    from oats.models import RunRuntimeState, TaskRuntimeRecord

    assert _type_hints(ConversationEvaluationCreateRequest)["provider"] == ProviderName
    assert _type_hints(ConversationEvaluationCreateRequest)["scope"] == EvaluationScope
    assert _type_hints(ConversationEvaluationResponse)["status"] == EvaluationStatus
    assert _type_hints(ConversationEvaluationRecord)["provider"] == ProviderName
    assert _type_hints(EvaluationJobRequest)["provider"] == ProviderName
    assert _type_hints(EvaluationJobResult)["status"] == EvaluationStatus
    assert _type_hints(DatabaseStatusResponse)["status"] == DatabaseRefreshStatus
    assert _type_hints(DatabaseRuntimeResponse)["analytics_read_backend"] == RuntimeReadBackend
    assert _type_hints(OrchestrationRunResponse)["status"] == RunRuntimeStatus
    assert _type_hints(OrchestrationTaskResponse)["task_id"] == TaskId
    assert _type_hints(TaskRuntimeRecord)["status"] == TaskRuntimeStatus
    assert _type_hints(RunRuntimeState)["run_id"] == RunId
    assert ProviderSelection | None == _type_hints(
        __import__("helaicopter_api.schema.analytics", fromlist=["AnalyticsQueryParams"]).AnalyticsQueryParams
    )["provider"]


def test_wave_two_domain_catalog_exposes_nominal_ids_and_split_project_path_semantics() -> None:
    from helaicopter_api.ports.app_sqlite import HistoricalConversationSummary
    from helaicopter_api.ports.claude_fs import ProjectDir
    from helaicopter_api.schema.conversations import ConversationDetailResponse, ProjectResponse
    from helaicopter_api.schema.plans import PlanDetailResponse
    from helaicopter_db.utils import provider_for_project_path
    from helaicopter_domain.ids import ConversationId, EvaluationId, PlanId, PromptId, SessionId
    from helaicopter_domain.paths import (
        AbsoluteProjectPath,
        EncodedProjectKey,
        ProjectDisplayPath,
    )
    from helaicopter_domain.vocab import ProviderName

    evaluation_prompt_record = __import__(
        "helaicopter_api.ports.app_sqlite", fromlist=["EvaluationPromptRecord"]
    ).EvaluationPromptRecord
    conversation_evaluation_record = __import__(
        "helaicopter_api.ports.app_sqlite", fromlist=["ConversationEvaluationRecord"]
    ).ConversationEvaluationRecord

    assert _type_hints(HistoricalConversationSummary)["conversation_id"] == ConversationId
    assert _type_hints(HistoricalConversationSummary)["session_id"] == SessionId
    assert _type_hints(evaluation_prompt_record)["prompt_id"] == PromptId
    assert _type_hints(conversation_evaluation_record)["evaluation_id"] == EvaluationId
    assert _type_hints(PlanDetailResponse)["id"] == PlanId

    assert _type_hints(ConversationDetailResponse)["project_path"] == EncodedProjectKey
    assert _type_hints(ProjectResponse)["encoded_path"] == EncodedProjectKey
    assert _type_hints(ProjectResponse)["display_name"] == ProjectDisplayPath
    assert _type_hints(ProjectDir)["full_path"] == AbsoluteProjectPath
    assert _type_hints(provider_for_project_path)["project_path"] == EncodedProjectKey
    assert _type_hints(provider_for_project_path)["return"] == ProviderName


def test_wave_four_boundary_models_replace_public_raw_dicts_with_named_contracts() -> None:
    from helaicopter_api.ports.app_sqlite import (
        AppSqliteStore,
        HistoricalConversationPlan,
        HistoricalConversationPlanStep,
        HistoricalConversationTask,
        ProviderSubscriptionSettingUpdate,
        SubscriptionSettingsUpdate,
    )
    from helaicopter_api.ports.claude_fs import (
        ClaudeHistoryPastedContents,
        ClaudeTaskPayload,
        HistoryEntry,
        RawConversationEvent,
        RawConversationEventData,
        RawConversationMessage,
        TaskReader,
    )
    from helaicopter_api.schema.conversations import (
        ConversationMessageResponse,
        ConversationTaskResponse,
        HistoryEntryResponse,
        HistoryPastedContentsResponse,
        TaskListResponse,
    )

    assert _type_hints(HistoryEntryResponse)["pasted_contents"] == HistoryPastedContentsResponse | None
    assert _type_hints(TaskListResponse)["tasks"] == list[ConversationTaskResponse]
    assert _type_hints(HistoryEntry)["pasted_contents"] == ClaudeHistoryPastedContents | None
    assert _type_hints(RawConversationEvent)["message"] == RawConversationMessage | None
    assert _type_hints(RawConversationEvent)["data"] == RawConversationEventData | None
    assert _type_hints(TaskReader.read_tasks)["return"] == list[ClaudeTaskPayload]
    assert _type_hints(HistoricalConversationPlan)["steps"] == list[HistoricalConversationPlanStep]
    assert _type_hints(AppSqliteStore.get_historical_tasks_for_session)["return"] == list[HistoricalConversationTask] | None
    assert _type_hints(AppSqliteStore.update_subscription_settings)["updates"] == SubscriptionSettingsUpdate
    assert _type_hints(SubscriptionSettingsUpdate)["claude"] == ProviderSubscriptionSettingUpdate | None

    block_annotation = _type_hints(ConversationMessageResponse)["blocks"]
    assert get_origin(block_annotation) is list
    item_annotation = get_args(block_annotation)[0]
    assert get_origin(item_annotation) is Annotated
    union_annotation = get_args(item_annotation)[0]
    block_names = {member.__name__ for member in get_args(union_annotation)}
    assert block_names == {
        "ConversationTextBlockResponse",
        "ConversationThinkingBlockResponse",
        "ConversationToolCallBlockResponse",
    }

    targeted_files = [
        ROOT / "python" / "helaicopter_api" / "schema" / "conversations.py",
        ROOT / "python" / "helaicopter_api" / "ports" / "app_sqlite.py",
        ROOT / "python" / "helaicopter_api" / "ports" / "claude_fs.py",
    ]
    for path in targeted_files:
        content = path.read_text(encoding="utf-8")
        assert "dict[str, Any]" not in content
        assert "list[dict[" not in content


def test_wave_five_function_contracts_wrap_only_exported_service_boundaries() -> None:
    from helaicopter_api.application import (
        analytics,
        conversations,
        database,
        evaluation_prompts,
        evaluations,
        orchestration,
        plans,
        subscriptions,
    )
    from oats import runner

    decorated = [
        analytics.get_analytics,
        conversations.list_conversations,
        conversations.get_conversation,
        conversations.get_subagent_conversation,
        conversations.list_conversation_dags,
        conversations.get_conversation_dag,
        conversations.list_projects,
        conversations.list_history,
        conversations.get_tasks,
        database.read_database_status,
        database.trigger_database_refresh,
        evaluation_prompts.list_evaluation_prompts,
        evaluation_prompts.resolve_evaluation_prompt,
        evaluation_prompts.create_evaluation_prompt,
        evaluation_prompts.update_evaluation_prompt,
        evaluation_prompts.delete_evaluation_prompt,
        evaluations.list_conversation_evaluations,
        evaluations.create_conversation_evaluation,
        orchestration.list_oats_runs,
        plans.list_plans,
        plans.get_plan,
        subscriptions.get_subscription_settings,
        subscriptions.update_subscription_settings,
        runner.invoke_agent,
        runner.build_planner_prompt,
        runner.build_task_prompt,
        runner.build_merge_prompt,
    ]
    undecorated = [
        analytics._normalize_provider,
        conversations._compact_dict,
        database._coerce_status_payload,
        evaluation_prompts._to_response,
        evaluations._to_response,
        orchestration._merge_run,
        plans._decode_plan_id,
        subscriptions._to_response,
        runner._run_command,
    ]

    assert all(hasattr(function, "raw_function") for function in decorated)
    assert all(not hasattr(function, "raw_function") for function in undecorated)


def test_wave_five_function_contracts_enforce_strict_inputs() -> None:
    from helaicopter_api.application.conversations import list_history
    from helaicopter_api.bootstrap.services import BackendServices
    from oats.models import AgentCommand, PlannedTask
    from oats.runner import build_task_prompt, invoke_agent

    services = object.__new__(BackendServices)
    task = PlannedTask(
        id="strict-task",
        title="Strict task",
        prompt="Implement the strict boundary.",
        branch_name="codex/oats/task/strict-task",
        pr_base="codex/oats/run",
    )

    with pytest.raises(ValidationError):
        list_history(services, limit="10")

    with pytest.raises(ValidationError):
        build_task_prompt(task, "Run: Strict", read_only="false")

    with pytest.raises(ValidationError):
        invoke_agent(
            agent_name=123,
            agent_command=AgentCommand(command="codex", args=["exec"]),
            role="executor",
            cwd=Path("."),
            prompt="Run the task.",
        )


def test_wave_nine_retires_rollout_compatibility_shims_or_tracks_them_with_dates() -> None:
    oats_models = (ROOT / "python" / "oats" / "models.py").read_text(encoding="utf-8")
    db_settings = (ROOT / "python" / "helaicopter_db" / "settings.py").read_text(encoding="utf-8")
    rollout_doc = ROLLOUT_DOC.read_text(encoding="utf-8")

    assert "migrate_legacy_fields" not in oats_models
    assert "def sqlite_artifact(" not in db_settings
    assert "def legacy_duckdb_artifact(" not in db_settings
    assert "analyticsReadBackend" in rollout_doc
    assert "conversationSummaryReadBackend" in rollout_doc
    assert "duckdb" in rollout_doc
    assert "2026-06-30" in rollout_doc


def test_wave_ten_schema_alias_policy_serializes_responses_and_rejects_wrong_inputs() -> None:
    from helaicopter_api.schema.database import DatabaseRefreshRequest, DatabaseRuntimeResponse

    request = DatabaseRefreshRequest.model_validate(
        {
            "force": True,
            "trigger": "manual",
            "staleAfterSeconds": 120,
        }
    )

    assert request.stale_after_seconds == 120

    with pytest.raises(ValidationError):
        DatabaseRefreshRequest.model_validate({"stale_after_seconds": 120})

    with pytest.raises(ValidationError):
        DatabaseRefreshRequest.model_validate({"force": True, "unexpected": True})

    response = DatabaseRuntimeResponse(
        analytics_read_backend="legacy",
        conversation_summary_read_backend="legacy",
    )

    assert response.model_dump() == {
        "analyticsReadBackend": "legacy",
        "conversationSummaryReadBackend": "legacy",
    }


def test_wave_ten_documents_green_required_scope_and_next_pyright_expansion_schedule() -> None:
    content = BASELINE_DOC.read_text(encoding="utf-8")

    assert "pyright is required for the scoped backend surface." in content
    assert "Next planned pyright expansion, only after this required scope stays green:" in content
    assert "`tests/`" in content
    assert "`python/helaicopter_db`" in content
