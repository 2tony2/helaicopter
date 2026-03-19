from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from helaicopter_domain.ids import RunId, SessionId, TaskId
from helaicopter_domain.vocab import ProviderName, RunRuntimeStatus, TaskRuntimeStatus


class RepoSettings(BaseModel):
    base_branch: str = "main"
    worktree_dir: str = ".oats-worktrees"
    default_concurrency: int = Field(default=3, ge=1)


class AgentsSettings(BaseModel):
    planner: ProviderName = "codex"
    executor: ProviderName = "claude"
    conflict_resolver: ProviderName = "claude"
    merge_operator: ProviderName = "codex"


class AgentCommand(BaseModel):
    command: str
    args: list[str] = []


class ValidationSettings(BaseModel):
    commands: list[str] = []
    fail_fast: bool = True


class GitSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_branch_prefix: str = "oats/task/"
    integration_branch_prefix: str = "oats/overnight/"
    integration_branch_base: str = "main"
    final_pr_target: str = "main"
    auto_push: bool = True
    auto_create_task_prs: bool = True
    auto_merge_task_prs_into_integration: bool = False
    auto_create_final_pr: bool = True
    require_manual_final_review: bool = True
    delete_worktree_on_success: bool = True


class ConflictSettings(BaseModel):
    enabled: bool = True
    max_resolution_attempts: int = Field(default=2, ge=0)
    revalidate_after_resolution: bool = True


class PlannerSettings(BaseModel):
    allow_inferred_dependencies: bool = True
    prefer_explicit_dependencies: bool = True


class ExecutionSettings(BaseModel):
    max_task_attempts: int = Field(default=2, ge=1)
    retry_backoff_seconds: float = Field(default=2.0, ge=0)


class LoggingSettings(BaseModel):
    session_dir: str = "~/.overnightoats/sessions"
    persist_format: str = "sqlite"
    write_markdown_report: bool = True


class ContextSettings(BaseModel):
    instruction_files: list[str] = Field(default_factory=lambda: ["AGENTS.md"])


class RepoConfig(BaseModel):
    repo: RepoSettings = Field(default_factory=RepoSettings)
    agents: AgentsSettings = Field(default_factory=AgentsSettings)
    agent: dict[str, AgentCommand] = {}
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    git: GitSettings = Field(default_factory=GitSettings)
    conflicts: ConflictSettings = Field(default_factory=ConflictSettings)
    planner: PlannerSettings = Field(default_factory=PlannerSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)

    @model_validator(mode="after")
    def validate_agent_refs(self) -> "RepoConfig":
        referenced = {
            self.agents.planner,
            self.agents.executor,
            self.agents.conflict_resolver,
            self.agents.merge_operator,
        }
        missing = sorted(name for name in referenced if name not in self.agent)
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing agent command definitions for: {joined}")
        return self


class TaskSpec(BaseModel):
    id: str
    title: str | None = None
    prompt: str
    depends_on: list[str] = []
    agent: ProviderName | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    acceptance_criteria: list[str] = []
    notes: list[str] = []
    validation_override: list[str] = []
    raw_body: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Task id cannot be empty")
        return cleaned


class RunSpec(BaseModel):
    title: str
    tasks: list[TaskSpec]
    source_path: Path

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "RunSpec":
        seen: set[str] = set()
        duplicates: list[str] = []
        for task in self.tasks:
            if task.id in seen:
                duplicates.append(task.id)
            seen.add(task.id)
        if duplicates:
            joined = ", ".join(sorted(set(duplicates)))
            raise ValueError(f"Duplicate task ids found: {joined}")
        return self


class PlannedTask(BaseModel):
    id: str
    title: str
    prompt: str
    depends_on: list[str] = []
    agent: ProviderName
    model: str | None = None
    reasoning_effort: str | None = None
    acceptance_criteria: list[str] = []
    validation_commands: list[str] = []
    branch_name: str
    pr_base: str


class ExecutionPlan(BaseModel):
    run_title: str
    repo_root: Path
    config_path: Path
    run_spec_path: Path
    integration_branch: str
    task_pr_target: str
    final_pr_target: str
    integration_branch_base: str
    require_manual_final_review: bool
    final_pr_title: str
    tasks: list[PlannedTask]


class PullRequestPlan(BaseModel):
    role: Literal["task", "final"]
    title: str
    head_branch: str
    base_branch: str
    body: str
    draft: bool = False
    task_id: TaskId | None = None


class CommandExecutionRecord(BaseModel):
    label: str
    command: list[str]
    cwd: Path
    executed: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    agent: ProviderName | None = None
    session_id: SessionId | None = None
    session_id_field: str | None = None
    timed_out: bool = False


class PullRequestApplyRecord(BaseModel):
    run_title: str
    repo_root: Path
    config_path: Path
    run_spec_path: Path
    integration_branch: str
    final_pr_target: str
    auto_merge_enabled: bool
    final_pr_created: bool
    executed: bool
    commands: list[CommandExecutionRecord] = []
    record_path: Path | None = None
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentInvocationResult(BaseModel):
    agent: ProviderName
    role: Literal["planner", "executor", "conflict_resolver", "merge_operator"]
    command: list[str]
    cwd: Path
    prompt: str
    session_id: SessionId | None = None
    session_id_field: str | None = None
    requested_session_id: SessionId | None = None
    output_text: str = ""
    raw_stdout: str = ""
    raw_stderr: str = ""
    exit_code: int
    timed_out: bool = False
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskExecutionRecord(BaseModel):
    task_id: TaskId
    title: str
    depends_on: list[str] = []
    invocation: AgentInvocationResult


class RunExecutionRecord(BaseModel):
    run_id: RunId | None = None
    run_title: str
    repo_root: Path
    config_path: Path
    run_spec_path: Path
    mode: Literal["read-only", "writable"] = "read-only"
    integration_branch: str
    task_pr_target: str
    final_pr_target: str
    planner: AgentInvocationResult | None = None
    tasks: list[TaskExecutionRecord] = []
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    record_path: Path | None = None

class InvocationRuntimeRecord(BaseModel):
    agent: ProviderName
    role: Literal["planner", "executor", "conflict_resolver", "merge_operator"]
    command: list[str] = []
    cwd: Path
    prompt: str
    session_id: SessionId | None = None
    session_id_field: str | None = None
    requested_session_id: SessionId | None = None
    output_text: str = ""
    raw_stdout: str = ""
    raw_stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    started_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_progress_event_at: datetime | None = None
    finished_at: datetime | None = None


class TaskRuntimeRecord(BaseModel):
    task_id: TaskId
    title: str
    depends_on: list[str] = []
    branch_name: str
    pr_base: str
    agent: ProviderName
    role: Literal["executor"] = "executor"
    status: TaskRuntimeStatus = "pending"
    attempts: int = 0
    invocation: InvocationRuntimeRecord | None = None


class RunPlanSnapshot(BaseModel):
    contract_version: Literal["oats-plan-v1"] = "oats-plan-v1"
    run_id: RunId
    run_title: str
    repo_root: Path
    config_path: Path
    run_spec_path: Path
    mode: Literal["read-only", "writable"] = "read-only"
    integration_branch: str
    task_pr_target: str
    final_pr_target: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tasks: list[PlannedTask] = []


class RuntimeProgressEvent(BaseModel):
    contract_version: Literal["oats-event-v1"] = "oats-event-v1"
    run_id: RunId
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    run_status: RunRuntimeStatus
    task_id: TaskId | None = None
    message: str | None = None
    agent: ProviderName | None = None
    session_id: SessionId | None = None
    heartbeat_at: datetime | None = None
    output_text: str | None = None


class RunRuntimeState(BaseModel):
    contract_version: Literal["oats-runtime-v1"] = "oats-runtime-v1"
    run_id: RunId
    run_title: str
    repo_root: Path
    config_path: Path
    run_spec_path: Path
    mode: Literal["read-only", "writable"] = "read-only"
    integration_branch: str
    task_pr_target: str
    final_pr_target: str
    runtime_dir: Path
    status: RunRuntimeStatus = "pending"
    active_task_id: TaskId | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    heartbeat_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    planner: InvocationRuntimeRecord | None = None
    tasks: list[TaskRuntimeRecord] = []
    final_record_path: Path | None = None
