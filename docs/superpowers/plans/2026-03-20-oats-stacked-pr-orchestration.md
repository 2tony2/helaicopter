# Oats Stacked PR Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-class stacked task-PR orchestration model in Oats, persist it through runtime and legacy orchestration artifacts, expose it through the backend, and render / operate it from the orchestration UI.

**Architecture:** Extend the existing Oats runtime and legacy orchestration artifact contracts to a v2 branch / PR control plane instead of introducing a separate ledger. Keep the core orchestration truth file-backed under `.oats/`, add explicit run-scoped refresh / resume actions for GitHub snapshot advancement, and let the FastAPI + Next.js layers consume one normalized run graph that includes both execution and stacked-PR state.

**Tech Stack:** Python 3.13, Typer, Pydantic, legacy orchestration 3, FastAPI, Next.js 16, React 19, SWR, `pytest`, `node:test`, `tsx`, ESLint

---

## File Structure

**Create:**
- `python/oats/stacked_prs.py` — pure helpers for parent-branch derivation, task PR merge-gate evaluation, run `stack_status` summaries, and retarget sequencing.
- `tests/oats/test_stacked_prs.py` — unit coverage for stacked branch ancestry, merge-gated multi-dependency tasks, and run / task status layering.
- `tests/oats/test_pr_actions.py` — unit coverage for run-scoped refresh / resume orchestration, GitHub snapshot parsing, merge-commit-only behavior, and child-PR retargeting.
- `python/helaicopter_api/application/oats_run_actions.py` — backend-owned refresh / resume actions that call Oats runtime code and return updated run records.
- `src/components/orchestration/oats-view-model.ts` — pure UI derivation helpers for run cards, node badges, stacked-PR entries, and waiting-state summaries.
- `src/components/orchestration/oats-view-model.test.ts` — `node:test` coverage for the pure orchestration view-model helpers.
- `src/components/orchestration/oats-pr-stack.tsx` — stacked-PR inspector component for the selected run/task.

**Modify:**
- `python/oats/models.py` — v2 run / task / PR snapshot fields, stack status, review snapshots, and action records.
- `python/oats/planner.py` — parent-branch planning, multi-dependency merge gating, and `ExecutionPlan` enrichment.
- `python/oats/run_definition.py` — canonical task execution hints for merge-gated task scheduling.
- `python/oats/pr.py` — PR snapshot refresh, merge-commit-only merge orchestration, child retargeting, and final-PR status capture.
- `python/oats/runtime_state.py` — runtime v2 serialization, branch / PR event emission, and run `stack_status` handling.
- `python/oats/cli.py` — run-scoped `refresh` / `resume` behavior, status rendering, and persisted PR action recording.
- `python/oats/legacy-orchestration/models.py` — add run-owned repo / PR context to payloads and task checkpoints.
- `python/oats/legacy-orchestration/compiler.py` — compile stacked-PR repo context into legacy orchestration task payloads.
- `python/oats/legacy-orchestration/worktree.py` — derive / reuse parent branches and stable worktree paths from the new task repo context.
- `python/oats/legacy-orchestration/artifacts.py` — persist task PR snapshots, review snapshots, and run IDs into local flow-run artifacts.
- `python/oats/legacy-orchestration/tasks.py` — merge-gated task execution and task-level artifact updates.
- `python/oats/legacy-orchestration/flows.py` — block multi-dependency tasks until upstream PR merges, not just upstream executor success.
- `python/helaicopter_api/schema/orchestration.py` — expose feature branch, task PR, final PR, operation history, and action response fields.
- `python/helaicopter_api/application/orchestration.py` — normalize runtime, run-record, and legacy orchestration artifact state into one orchestration response.
- `python/helaicopter_api/router/orchestration.py` — add refresh / resume mutation routes and response wiring.
- `tests/test_repo_config.py` — extend planning / dry-run expectations for stacked PR bases and merge policy.
- `tests/test_runtime_state.py` — cover runtime v2 persistence and new events.
- `tests/oats/test_legacy-orchestration_worktree.py` — cover parent-branch-aware worktree prep.
- `tests/oats/test_legacy-orchestration_tasks.py` — cover task artifact snapshots and merge-gated execution details.
- `tests/oats/test_legacy-orchestration_flows.py` — cover flow-level merge gating and `run_id` propagation.
- `tests/test_api_orchestration.py` — cover enriched run payloads and refresh / resume routes.
- `src/lib/types.ts` — add stacked-PR frontend types.
- `src/lib/client/endpoints.ts` — add orchestration refresh / resume endpoints.
- `src/lib/client/mutations.ts` — add refresh / resume client mutations.
- `src/lib/client/mutations.test.ts` — cover refresh / resume request / response normalization.
- `src/lib/client/normalize.ts` — normalize new backend branch / PR payloads.
- `src/lib/client/normalize.test.ts` — cover v2 orchestration normalization.
- `src/components/orchestration/overnight-oats-panel.tsx` — render run summaries, node badges, stacked-PR inspector, and refresh / resume actions.
- `docs/orchestration/overview.mdx` — document the new orchestration control-plane behavior.
- `docs/orchestration/oats.mdx` — document the stacked-PR runtime and manual final-review gate.
- `public/openapi/helaicopter-api.json`
- `public/openapi/helaicopter-api.yaml`

**Implementation notes:**
- Use `@test-driven-development` for every task below. Tests should fail before implementation changes.
- Use `@verification-before-completion` before claiming the feature is complete.
- Keep derived analytics out of this plan. Only deliver the operational control plane and UI.

### Task 1: Model Stacked PR Planning and Status Layers

**Files:**
- Create: `python/oats/stacked_prs.py`
- Create: `tests/oats/test_stacked_prs.py`
- Modify: `python/oats/models.py`
- Modify: `python/oats/planner.py`
- Modify: `python/oats/run_definition.py`
- Modify: `python/oats/legacy-orchestration/models.py`
- Test: `tests/test_repo_config.py`
- Test: `tests/oats/test_stacked_prs.py`
- Test: `tests/oats/test_legacy-orchestration_worktree.py`

- [ ] **Step 1: Write the failing planner and status-layer tests**

```python
def test_execution_plan_uses_dependency_parent_branch_targets() -> None:
    plan = build_execution_plan(config=config, run_spec=run, repo_root=repo_root, config_path=config_path)

    auth = next(task for task in plan.tasks if task.id == "auth")
    dashboard = next(task for task in plan.tasks if task.id == "dashboard_api")

    assert auth.parent_branch == plan.integration_branch
    assert dashboard.parent_branch == auth.branch_name
    assert dashboard.pr_base == auth.branch_name


def test_multi_dependency_task_starts_merge_blocked() -> None:
    graph = derive_stacked_pr_graph(plan.tasks)
    verify = graph["verify"]

    assert verify.branch_strategy == "after_dependency_merges"
    assert verify.initial_task_status == "blocked"
```

- [ ] **Step 2: Run the targeted Python tests and confirm they fail**

Run: `uv run --group dev pytest tests/test_repo_config.py tests/oats/test_stacked_prs.py tests/oats/test_legacy-orchestration_worktree.py -q`
Expected: FAIL with missing `parent_branch`, missing stacked-PR helper functions, and mismatched `pr_base` assertions.

- [ ] **Step 3: Implement the pure stacked-PR helper layer and v2 planning fields**

```python
class PlannedTask(BaseModel):
    id: str
    title: str
    branch_name: str
    parent_branch: str
    pr_base: str
    branch_strategy: Literal["feature_base", "single_parent", "after_dependency_merges"]
    initial_task_status: TaskRuntimeStatus


def derive_parent_branch(task: TaskSpec, *, feature_branch: str, upstream_branch_map: dict[str, str]) -> tuple[str, str]:
    if not task.depends_on:
        return feature_branch, "feature_base"
    if len(task.depends_on) == 1:
        return upstream_branch_map[task.depends_on[0]], "single_parent"
    return feature_branch, "after_dependency_merges"
```

- [ ] **Step 4: Re-run the targeted Python tests and confirm they pass**

Run: `uv run --group dev pytest tests/test_repo_config.py tests/oats/test_stacked_prs.py tests/oats/test_legacy-orchestration_worktree.py -q`
Expected: PASS

- [ ] **Step 5: Commit the planning-model slice**

```bash
git add python/oats/stacked_prs.py python/oats/models.py python/oats/planner.py python/oats/run_definition.py python/oats/legacy-orchestration/models.py tests/test_repo_config.py tests/oats/test_stacked_prs.py tests/oats/test_legacy-orchestration_worktree.py
git commit -m "feat: model stacked PR planning"
```

### Task 2: Persist Runtime PR State and Run-Scoped Refresh / Resume Actions

**Files:**
- Create: `tests/oats/test_pr_actions.py`
- Modify: `python/oats/models.py`
- Modify: `python/oats/pr.py`
- Modify: `python/oats/runtime_state.py`
- Modify: `python/oats/cli.py`
- Test: `tests/test_runtime_state.py`
- Test: `tests/test_repo_config.py`
- Test: `tests/oats/test_pr_actions.py`

- [ ] **Step 1: Write failing tests for runtime v2 fields, final PR lifecycle, retargeting, conflict history, and run-scoped refresh / resume**

```python
def test_refresh_run_updates_waiting_task_prs_and_advances_merge_ready_items(tmp_path: Path) -> None:
    state = build_initial_runtime_state(
        execution_plan=execution_plan,
        mode="writable",
        run_id="run-123",
        executor_agent="codex",
    )
    state.stack_status = "awaiting_task_merge"
    state.tasks[0].task_pr = TaskPullRequestSnapshot(state="open", merge_gate_status="awaiting_checks")
    state.final_pr = FinalPullRequestSnapshot(state="open", review_gate_status="awaiting_human")

    refreshed = refresh_run(state=state, github_client=stub_client_with_passing_checks())

    assert refreshed.tasks[0].task_pr.merge_gate_status == "merged"
    assert refreshed.stack_status in {"building", "ready_for_final_review"}


def test_runtime_state_persists_task_review_summary(tmp_path: Path) -> None:
    state = build_initial_runtime_state(
        execution_plan=execution_plan,
        mode="writable",
        run_id="run-123",
        executor_agent="codex",
    )
    state.tasks[0].task_pr.review_summary = ReviewSummary(blocking_state="changes_requested")
    path = write_runtime_state(state)
    loaded = load_runtime_state(path)

    assert loaded.tasks[0].task_pr.review_summary.blocking_state == "changes_requested"


def test_refresh_run_retargets_open_child_prs_after_parent_merge() -> None:
    refreshed = refresh_run(state=stacked_state_with_parent_merge(), github_client=stub_child_pr_client())

    child = next(task for task in refreshed.tasks if task.task_id == "dashboard_api")
    assert child.task_pr.base_branch == refreshed.feature_branch.name
    assert any(entry.kind == "pr_retarget" for entry in refreshed.tasks[0].operation_history)


def test_resume_run_reuses_existing_stack_and_marks_run_completed_when_final_pr_is_merged() -> None:
    resumed = resume_run(
        run_id="run-123",
        repo_root=tmp_path,
        github_client=stub_final_pr_merged_client(),
    )

    assert resumed.run_id == "run-123"
    assert resumed.feature_branch.name == "oats/overnight/run-auth-and-dashboard"
    assert resumed.final_pr.state == "merged"
    assert resumed.final_pr.snapshot_source == "github_cli"
    assert resumed.final_pr.checks_summary["state"] == "success"
    assert resumed.status == "completed"
    assert resumed.stack_status == "completed"


def test_merge_failure_records_conflict_resolution_history() -> None:
    refreshed = refresh_run(state=state_with_merge_conflict(), github_client=stub_conflict_client())

    assert refreshed.stack_status == "resolving_conflict"
    assert refreshed.active_operation.kind == "conflict_resolution"
    assert refreshed.active_operation.started_at is not None
    assert any(entry.kind == "conflict_resolution" for entry in refreshed.tasks[0].operation_history)


def test_refresh_run_creates_final_pr_when_the_last_task_pr_merges() -> None:
    refreshed = refresh_run(
        state=state_with_last_merge_ready_task(),
        github_client=stub_final_pr_create_client(),
    )

    assert refreshed.final_pr.state == "open"
    assert refreshed.final_pr.review_gate_status == "awaiting_human"
    assert refreshed.final_pr.last_refreshed_at is not None
    assert refreshed.stack_status == "ready_for_final_review"


def test_resume_run_unblocks_merge_gated_multi_dependency_tasks_after_upstream_prs_merge() -> None:
    resumed = resume_run(
        run_id="run-123",
        repo_root=tmp_path,
        github_client=stub_upstream_merged_client(),
    )

    verify = next(task for task in resumed.tasks if task.task_id == "verify")
    assert verify.status == "pending"
    assert verify.parent_branch == resumed.feature_branch.name
```

- [ ] **Step 2: Run the targeted runtime and PR-action tests and confirm they fail**

Run: `uv run --group dev pytest tests/test_runtime_state.py tests/test_repo_config.py tests/oats/test_pr_actions.py -q`
Expected: FAIL with missing PR snapshot models, missing `final_pr`, missing retarget / conflict events, and no run-scoped refresh / resume implementation.

- [ ] **Step 3: Implement runtime v2 persistence, GitHub snapshot parsing, final PR tracking, child retargeting, and CLI refresh / resume**

```python
class TaskPullRequestSnapshot(BaseModel):
    number: int | None = None
    url: str | None = None
    state: Literal["not_created", "open", "merged", "closed", "blocked"] = "not_created"
    merge_gate_status: Literal["not_ready", "awaiting_checks", "awaiting_review_clearance", "merge_ready", "merged"] = "not_ready"
    mergeability: str | None = None
    checks_summary: dict[str, object] = {}
    review_summary: dict[str, object] = {}
    snapshot_source: str | None = None
    last_refreshed_at: datetime | None = None
    is_stale: bool = False


class FinalPullRequestSnapshot(BaseModel):
    number: int | None = None
    url: str | None = None
    state: Literal["not_created", "open", "ready_for_review", "merged", "closed"] = "not_created"
    review_gate_status: Literal["not_created", "awaiting_human", "merged"] = "not_created"
    checks_summary: dict[str, object] = {}
    snapshot_source: str | None = None
    last_refreshed_at: datetime | None = None
    is_stale: bool = False


class OperationHistoryEntry(BaseModel):
    kind: Literal["pr_create", "pr_merge", "pr_retarget", "conflict_resolution", "refresh", "resume"]
    status: Literal["started", "succeeded", "failed"]
    session_id: str | None = None
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def refresh_run(state: RunRuntimeState, github_client: GitHubClient, *, action: str = "refresh") -> RunRuntimeState:
    waiting_tasks = sorted(waiting_task_ids, key=topological_index.__getitem__)
    for task_id in waiting_tasks:
        snapshot = github_client.read_pr(task_pr.number)
        persist_task_pr_snapshot(state, task_id, snapshot)
        if merge_policy_allows(snapshot):
            merge_task_pr(state, task_id, snapshot, merge_method="merge_commit")
            retarget_child_prs(state, merged_task_id=task_id, github_client=github_client)
    if should_create_final_pr(state):
        create_final_pr(state, github_client)
        state.stack_status = "ready_for_final_review"
    refresh_final_pr_snapshot(state, github_client)
    if state.final_pr.state == "merged":
        state.status = "completed"
        state.stack_status = "completed"


def resume_run(run_id: str, repo_root: Path, github_client: GitHubClient) -> RunRuntimeState:
    state = resolve_runtime_state(repo_root, run_id=run_id)
    refreshed = refresh_run(state=state, github_client=github_client, action="resume")
    for task in refreshed.tasks:
        if task.status == "blocked" and merge_gate_is_clear(task, refreshed.tasks):
            task.status = "pending"
    return refreshed
```

- [ ] **Step 4: Re-run the targeted runtime and PR-action tests and confirm they pass**

Run: `uv run --group dev pytest tests/test_runtime_state.py tests/test_repo_config.py tests/oats/test_pr_actions.py -q`
Expected: PASS

- [ ] **Step 5: Commit the runtime / CLI slice**

```bash
git add python/oats/models.py python/oats/pr.py python/oats/runtime_state.py python/oats/cli.py tests/test_runtime_state.py tests/test_repo_config.py tests/oats/test_pr_actions.py
git commit -m "feat: persist stacked PR runtime state"
```

### Task 3: Gate legacy orchestration Execution on PR Stack State and Persist Attempt Snapshots

**Files:**
- Modify: `python/oats/legacy-orchestration/models.py`
- Modify: `python/oats/legacy-orchestration/compiler.py`
- Modify: `python/oats/legacy-orchestration/worktree.py`
- Modify: `python/oats/legacy-orchestration/artifacts.py`
- Modify: `python/oats/legacy-orchestration/tasks.py`
- Modify: `python/oats/legacy-orchestration/flows.py`
- Test: `tests/oats/test_legacy-orchestration_worktree.py`
- Test: `tests/oats/test_legacy-orchestration_tasks.py`
- Test: `tests/oats/test_legacy-orchestration_flows.py`

- [ ] **Step 1: Write failing legacy orchestration tests for merge-gated tasks and artifact snapshots**

```python
def test_execute_compiled_flow_graph_blocks_multi_dependency_task_until_upstream_pr_merges(tmp_path: Path) -> None:
    payload = _payload_with_multi_dependency_task(tmp_path)
    result = execute_compiled_flow_graph(payload, executor=executor, flow_run_id="flow-run-1")

    assert result.task_results["verify"].status == "blocked"
    assert json.loads((result.artifact_root / "tasks" / "verify.json").read_text())["merge_gate_status"] == "not_ready"


def test_task_checkpoint_persists_run_id_parent_branch_and_task_pr_snapshot(tmp_path: Path) -> None:
    checkpoint = json.loads((artifact_store.paths.tasks_dir / "build.json").read_text())
    assert checkpoint["run_id"] == "run-123"
    assert checkpoint["parent_branch"] == "oats/task/plan"
    assert checkpoint["task_pr"]["state"] == "open"


def test_flow_run_metadata_persists_run_id_for_backend_joining(tmp_path: Path) -> None:
    metadata = json.loads((artifact_store.paths.metadata_path).read_text())
    assert metadata["run_id"] == "run-123"
    assert metadata["flow_run_id"] == "flow-run-1"
```

- [ ] **Step 2: Run the targeted legacy orchestration tests and confirm they fail**

Run: `uv run --group dev pytest tests/oats/test_legacy-orchestration_worktree.py tests/oats/test_legacy-orchestration_tasks.py tests/oats/test_legacy-orchestration_flows.py -q`
Expected: FAIL with missing `run_id`, missing parent-branch persistence, and no merge-gated task behavior.

- [ ] **Step 3: Implement legacy orchestration payload, flow, and artifact updates**

```python
class legacy orchestrationTaskRepoContext(BaseModel):
    integration_branch: str
    task_branch: str
    parent_branch: str
    worktree_path: Path


class LocalFlowRunMetadata(BaseModel):
    run_id: str
    flow_run_id: str
    run_title: str


if not upstream_prs_merged(task_node, artifact_store):
    artifact_store.write_task_checkpoint(
        task_node,
        status="blocked",
        attempt=resolved_attempt,
        upstream_task_ids=sorted(upstream_results),
    )
    return CompiledTaskResult(task_id=task_node.task_id, attempt=resolved_attempt, status="blocked")
```

- [ ] **Step 4: Re-run the targeted legacy orchestration tests and confirm they pass**

Run: `uv run --group dev pytest tests/oats/test_legacy-orchestration_worktree.py tests/oats/test_legacy-orchestration_tasks.py tests/oats/test_legacy-orchestration_flows.py -q`
Expected: PASS

- [ ] **Step 5: Commit the legacy orchestration slice**

```bash
git add python/oats/legacy-orchestration/models.py python/oats/legacy-orchestration/compiler.py python/oats/legacy-orchestration/worktree.py python/oats/legacy-orchestration/artifacts.py python/oats/legacy-orchestration/tasks.py python/oats/legacy-orchestration/flows.py tests/oats/test_legacy-orchestration_worktree.py tests/oats/test_legacy-orchestration_tasks.py tests/oats/test_legacy-orchestration_flows.py
git commit -m "feat: gate legacy-orchestration flow tasks on PR stack state"
```

### Task 4: Expose Stacked PR State and Actions Through the Backend

**Files:**
- Create: `python/helaicopter_api/application/oats_run_actions.py`
- Modify: `python/helaicopter_api/schema/orchestration.py`
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/router/orchestration.py`
- Test: `tests/test_api_orchestration.py`

- [ ] **Step 1: Write failing API tests for enriched GET payloads and refresh / resume routes**

```python
def test_orchestration_oats_index_includes_feature_branch_and_task_prs(tmp_path: Path) -> None:
    response = client.get("/orchestration/oats")
    payload = response.json()[0]

    assert payload["featureBranch"]["name"] == "oats/overnight/runtime-facts"
    assert payload["tasks"][0]["taskPr"]["mergeGateStatus"] == "awaiting_checks"
    assert payload["finalPr"]["reviewGateStatus"] == "awaiting_human"
    assert payload["tasks"][0]["operationHistory"][0]["kind"] == "pr_create"


def test_orchestration_refresh_route_returns_updated_run(tmp_path: Path) -> None:
    response = client.post("/orchestration/oats/oats-run-1/refresh")

    assert response.status_code == 200
    assert response.json()["stackStatus"] in {"building", "ready_for_final_review"}


def test_orchestration_resume_route_reuses_the_existing_run_stack(tmp_path: Path) -> None:
    response = client.post("/orchestration/oats/oats-run-1/resume")

    assert response.status_code == 200
    assert response.json()["runId"] == "oats-run-1"
    assert response.json()["featureBranch"]["name"] == "oats/overnight/runtime-facts"


def test_orchestration_payload_prefers_runtime_graph_over_terminal_record(tmp_path: Path) -> None:
    response = client.get("/orchestration/oats")
    payload = response.json()[0]

    assert payload["status"] == "running"
    assert payload["stackStatus"] == "awaiting_task_merge"
```

- [ ] **Step 2: Run the backend orchestration tests and confirm they fail**

Run: `uv run --group dev pytest tests/test_api_orchestration.py -q`
Expected: FAIL with missing schema fields and missing POST routes.

- [ ] **Step 3: Implement backend schema expansion, shaping, and action routes**

```python
@orchestration_router.post(
    "/oats/{run_id}/refresh",
    response_model=OrchestrationRunResponse,
    response_model_by_alias=True,
)
async def orchestration_oats_refresh(run_id: str, services: BackendServices = Depends(get_services)) -> OrchestrationRunResponse:
    return refresh_oats_run(services, run_id)


@orchestration_router.post(
    "/oats/{run_id}/resume",
    response_model=OrchestrationRunResponse,
    response_model_by_alias=True,
)
async def orchestration_oats_resume(run_id: str, services: BackendServices = Depends(get_services)) -> OrchestrationRunResponse:
    return resume_oats_run(services, run_id)
```

- [ ] **Step 4: Re-run the backend orchestration tests and confirm they pass**

Run: `uv run --group dev pytest tests/test_api_orchestration.py -q`
Expected: PASS

- [ ] **Step 5: Commit the backend slice**

```bash
git add python/helaicopter_api/application/oats_run_actions.py python/helaicopter_api/schema/orchestration.py python/helaicopter_api/application/orchestration.py python/helaicopter_api/router/orchestration.py tests/test_api_orchestration.py
git commit -m "feat: expose stacked PR orchestration actions"
```

### Task 5: Add Frontend Types, Mutations, View Models, and the PR Stack Inspector

**Files:**
- Create: `src/components/orchestration/oats-view-model.ts`
- Create: `src/components/orchestration/oats-view-model.test.ts`
- Create: `src/components/orchestration/oats-pr-stack.tsx`
- Modify: `src/lib/types.ts`
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/client/mutations.ts`
- Modify: `src/lib/client/mutations.test.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/normalize.test.ts`
- Modify: `src/components/orchestration/overnight-oats-panel.tsx`
- Test: `src/lib/client/normalize.test.ts`
- Test: `src/lib/client/mutations.test.ts`
- Test: `src/components/orchestration/oats-view-model.test.ts`
- Test: `src/components/orchestration/tabs.test.ts`

- [ ] **Step 1: Write failing node tests for orchestration normalization, mutations, and view-model derivation**

```ts
test("normalizeOvernightOatsRuns keeps stacked PR fields", () => {
  const run = normalizeOvernightOatsRuns([{
    runId: "run-1",
    featureBranch: { name: "oats/overnight/demo" },
    finalPr: { state: "open", reviewGateStatus: "awaiting_human" },
    stackStatus: "awaiting_task_merge",
    tasks: [{ taskId: "auth", taskPr: { mergeGateStatus: "awaiting_checks" }, operationHistory: [{ kind: "pr_create", status: "succeeded" }] }],
    dag: { nodes: [], edges: [], stats: { totalNodes: 0, totalEdges: 0, maxDepth: 0, maxBreadth: 0, rootCount: 0, providerBreakdown: {}, timedOutCount: 0, activeCount: 0, pendingCount: 0, failedCount: 0, succeededCount: 0 } }
  }])[0];
  assert.equal(run.featureBranch?.name, "oats/overnight/demo");
  assert.equal(run.tasks[0].taskPr?.mergeGateStatus, "awaiting_checks");
  assert.equal(run.finalPr?.reviewGateStatus, "awaiting_human");
});

test("buildOatsRunViewModel exposes run card summaries and stack entries", () => {
  const model = buildOatsRunViewModel(sampleRun);
  assert.equal(model.summaryLabel, "awaiting task merge");
  assert.equal(model.stackEntries[0].kind, "task-pr");
  assert.equal(model.finalReviewLabel, "awaiting human review");
});

test("refresh and resume mutations post to the orchestration action routes", async () => {
  await refreshOatsRun("run-1");
  await resumeOatsRun("run-1");
});

test("selecting a task keeps DAG and PR stack selection in sync", () => {
  const model = buildOatsRunViewModel(sampleRun, { selectedTaskId: "auth" });
  assert.equal(model.selectedNodeId, "auth");
  assert.equal(model.selectedStackEntry?.taskId, "auth");
});
```

- [ ] **Step 2: Run the targeted node tests and confirm they fail**

Run: `node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/mutations.test.ts src/components/orchestration/oats-view-model.test.ts src/components/orchestration/tabs.test.ts`
Expected: FAIL with missing types, missing mutation helpers, and missing view-model module.

- [ ] **Step 3: Implement client types, action helpers, and the stacked-PR UI components**

```ts
export interface TaskPullRequestSnapshot {
  number?: number;
  url?: string;
  state: "not_created" | "open" | "merged" | "closed" | "blocked";
  mergeGateStatus: "not_ready" | "awaiting_checks" | "awaiting_review_clearance" | "merge_ready" | "merged";
  reviewSummary?: { blockingState?: string; reviewers?: string[] };
}

export async function refreshOatsRun(runId: string): Promise<OvernightOatsRunRecord> {
  return post(endpoints.orchestrationOatsRefresh(runId), undefined, (value) =>
    normalizeOvernightOatsRuns([value])[0]
  );
}

export async function resumeOatsRun(runId: string): Promise<OvernightOatsRunRecord> {
  return post(endpoints.orchestrationOatsResume(runId), undefined, (value) =>
    normalizeOvernightOatsRuns([value])[0]
  );
}
```

- [ ] **Step 4: Re-run the targeted node tests and confirm they pass**

Run: `node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/mutations.test.ts src/components/orchestration/oats-view-model.test.ts src/components/orchestration/tabs.test.ts`
Expected: PASS

- [ ] **Step 5: Commit the frontend slice**

```bash
git add src/components/orchestration/oats-view-model.ts src/components/orchestration/oats-view-model.test.ts src/components/orchestration/oats-pr-stack.tsx src/lib/types.ts src/lib/client/endpoints.ts src/lib/client/mutations.ts src/lib/client/mutations.test.ts src/lib/client/normalize.ts src/lib/client/normalize.test.ts src/components/orchestration/overnight-oats-panel.tsx
git commit -m "feat: render stacked PR orchestration state"
```

### Task 6: Refresh OpenAPI and Orchestration Docs, Then Verify End-to-End

**Files:**
- Modify: `docs/orchestration/overview.mdx`
- Modify: `docs/orchestration/oats.mdx`
- Modify: `public/openapi/helaicopter-api.json`
- Modify: `public/openapi/helaicopter-api.yaml`

- [ ] **Step 1: Update orchestration docs to match the delivered behavior**

```md
- task PRs stack according to task dependencies
- refresh / resume is run-scoped and may advance multiple merge-ready task PRs
- the final feature PR remains a manual gate to `main`
```

- [ ] **Step 2: Regenerate the committed OpenAPI snapshots**

Run: `npm run api:openapi`
Expected: PASS and updated `public/openapi/helaicopter-api.json` / `public/openapi/helaicopter-api.yaml`

- [ ] **Step 3: Run the full Python verification suite for this feature**

Run: `uv run --group dev pytest tests/test_repo_config.py tests/test_runtime_state.py tests/oats/test_stacked_prs.py tests/oats/test_pr_actions.py tests/oats/test_legacy-orchestration_worktree.py tests/oats/test_legacy-orchestration_tasks.py tests/oats/test_legacy-orchestration_flows.py tests/test_api_orchestration.py -q`
Expected: PASS

- [ ] **Step 4: Run the full frontend verification suite for this feature**

Run: `node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/mutations.test.ts src/lib/client/legacy-orchestration-normalize.test.ts src/components/orchestration/tabs.test.ts src/components/orchestration/oats-view-model.test.ts`
Expected: PASS

- [ ] **Step 5: Run lint across the repo**

Run: `npm run lint`
Expected: PASS

- [ ] **Step 6: Commit the docs / artifact refresh**

```bash
git add docs/orchestration/overview.mdx docs/orchestration/oats.mdx public/openapi/helaicopter-api.json public/openapi/helaicopter-api.yaml
git commit -m "docs: refresh orchestration API and docs"
```
