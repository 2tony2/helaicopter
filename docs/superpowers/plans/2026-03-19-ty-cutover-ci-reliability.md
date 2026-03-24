# ty Cutover And CI Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `pyright` with `ty`, widen required type checking to all `python/**`, harden the Python quality workflow, and burn down the current `ty` backlog until `ruff`, `pytest`, and `ty` all pass locally.

**Architecture:** Keep the migration explicit and staged. First flip the repository contracts so tests, docs, config, workflow, and lockfile all describe `ty` as the only required type checker. Then fix the real `ruff` and `ty` failures in bounded clusters: low-risk hygiene and server wiring first, then the wider nominal-ID/literal narrowing work in API, DB, and OATS modules. Use the real CLI commands as the authoritative verification surface throughout.

**Tech Stack:** Python 3.13, uv, ty, Ruff, pytest, FastAPI, Pydantic v2, TypedDict, NewType

---

## File Structure Map

- Modify: `pyproject.toml`
- Modify: `.github/workflows/backend-quality.yml`
- Modify: `uv.lock`
- Modify: `docs/python-backend-type-system-baseline.md`
- Delete: `docs/superpowers/baselines/2026-03-18-python-backend-pyright-baseline.json`
- Modify: `tests/test_backend_type_system_rollout.py`
- Modify: `python/helaicopter_api/application/gateway.py`
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/application/legacy-orchestration_orchestration.py`
- Modify: `python/helaicopter_api/ports/legacy-orchestration.py`
- Modify: `python/helaicopter_api/server/dependencies.py`
- Modify: `python/helaicopter_api/server/main.py`
- Modify: `tests/oats/test_legacy-orchestration_deployments.py`
- Modify: `python/helaicopter_api/adapters/app_sqlite/store.py`
- Modify: `python/helaicopter_api/adapters/claude_fs/conversations.py`
- Modify: `python/helaicopter_api/adapters/evaluation_jobs.py`
- Modify: `python/helaicopter_api/application/analytics.py`
- Modify: `python/helaicopter_api/application/conversations.py`
- Modify: `python/helaicopter_api/application/database.py`
- Modify: `python/helaicopter_api/application/evaluation_prompts.py`
- Modify: `python/helaicopter_api/application/evaluations.py`
- Modify: `python/helaicopter_api/application/plans.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `python/helaicopter_api/pure/conversation_dag.py`
- Modify: `python/helaicopter_db/refresh.py`
- Modify: `python/helaicopter_db/status.py`
- Modify: `python/helaicopter_db/utils.py`
- Modify: `python/oats/cli.py`
- Modify: `python/oats/parser.py`
- Modify: `python/oats/pr.py`
- Modify: `python/oats/legacy-orchestration/compiler.py`
- Modify: `python/oats/legacy-orchestration/flows.py`
- Modify: `python/oats/legacy-orchestration/tasks.py`
- Modify: `python/oats/runner.py`

### Task 1: Rewrite Repository Contracts Around `ty`

**Files:**
- Modify: `tests/test_backend_type_system_rollout.py`
- Modify: `docs/python-backend-type-system-baseline.md`
- Delete: `docs/superpowers/baselines/2026-03-18-python-backend-pyright-baseline.json`
- Modify: `.github/workflows/backend-quality.yml`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Rewrite the guardrail tests to assert the new `ty` contract**

Update the constants and assertions in `tests/test_backend_type_system_rollout.py` so they describe the post-cutover baseline. Rewrite every `pyright`-specific assertion in the file, including the later wave-ten baseline-doc check near the bottom of the module:

```python
EXPECTED_DEV_DEPENDENCIES = {"httpx", "pytest", "pytest-cov", "ruff", "ty"}
EXPECTED_TY_ROOTS = ["python"]

def test_pyproject_commits_backend_tooling_baseline() -> None:
    pyproject = _load_pyproject()
    dev_group = pyproject["dependency-groups"]["dev"]
    assert EXPECTED_DEV_DEPENDENCIES.issubset(_package_names(dev_group))

    ty_environment = pyproject["tool"]["ty"]["environment"]
    assert ty_environment["python-version"] == "3.13"
    assert ty_environment["root"] == EXPECTED_TY_ROOTS
    assert "pyright" not in _package_names(dev_group)
    assert "pyright" not in pyproject["tool"]
```

Also rewrite the workflow/doc tests so they assert:

- `uv run --group dev ty check python --error-on-warning`
- no `pyright` command remains
- the baseline doc says `ty` is required for all `python/**`
- `tests/**` are explicitly deferred from required type checking

- [ ] **Step 2: Run the rewritten guardrail tests to confirm the current repo is red**

Run: `uv run --group dev pytest -q tests/test_backend_type_system_rollout.py`

Expected: FAIL because `pyproject.toml`, the workflow, and the baseline doc still reference `pyright`.

- [ ] **Step 3: Replace the tool dependency and config in `pyproject.toml`**

Swap the dev dependency and remove the old `pyright` section. Add `ty` configuration in `pyproject.toml` using the `tool.ty.environment` table:

```toml
[dependency-groups]
dev = [
  "httpx>=0.28.0",
  "pytest>=8.0.0",
  "pytest-cov>=6.0.0",
  "ruff>=0.11.0",
  "ty>=0.0.24",
]

[tool.ty.environment]
python-version = "3.13"
root = ["python"]
```

Keep the existing `ruff`, `pytest`, and setuptools configuration intact. Only add `extra-paths = ["python"]` if the first repo-local `ty check python` run proves the default module discovery is insufficient. If `tool.ty.environment` in `pyproject.toml` still cannot express the needed source-root behavior cleanly, fall back to a dedicated `ty.toml` exactly as allowed by the spec rather than layering on opaque CLI flags.

- [ ] **Step 4: Rewrite the baseline doc and remove the stale pyright artifact**

Update `docs/python-backend-type-system-baseline.md` so it is a current `ty` contract doc, not a historical `pyright` rollout record. The rewritten doc should:

- say `ty` is the only required type checker
- say the required scope is all `python/**`
- state that `tests/**` remain outside required type checking for now
- record the local verification commands:

```md
- `uv run --group dev ruff check python tests`
- `uv run --group dev pytest -q`
- `uv run --group dev ty check python --error-on-warning`
```

Delete `docs/superpowers/baselines/2026-03-18-python-backend-pyright-baseline.json` outright rather than leaving a pyright-named artifact in the active contract path.

- [ ] **Step 5: Replace the workflow’s type-check job and refresh path triggers**

Rewrite `.github/workflows/backend-quality.yml` so the third job is `ty` rather than `pyright`:

```yaml
  ty:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: astral-sh/setup-uv@v6
      - name: Sync dev environment
        run: uv sync --group dev
      - name: ty
        run: uv run --group dev ty check python --error-on-warning
```

Also remove the deleted baseline JSON path from the workflow triggers.

- [ ] **Step 6: Refresh the lockfile**

Run: `uv lock`

Expected: `uv.lock` no longer includes `pyright` and now pins `ty`.

- [ ] **Step 7: Re-run the guardrail tests**

Run: `uv run --group dev pytest -q tests/test_backend_type_system_rollout.py`

Expected: PASS. The repository contracts now describe `ty` rather than `pyright`.

- [ ] **Step 8: Run the widened type-check command once to confirm the real post-cutover backlog**

Run: `uv run --group dev ty check python --output-format concise --error-on-warning`

Expected: FAIL, but now on the true all-`python/**` backlog rather than on stale repo-contract drift. Use this output to confirm the remaining work is covered by Tasks 2-5 before moving on.

- [ ] **Step 9: Commit the contract flip**

```bash
git add pyproject.toml uv.lock .github/workflows/backend-quality.yml \
  docs/python-backend-type-system-baseline.md \
  tests/test_backend_type_system_rollout.py \
  docs/superpowers/baselines/2026-03-18-python-backend-pyright-baseline.json
git commit -m "chore: replace pyright with ty"
```

### Task 2: Clear The Current Ruff Backlog And Low-Risk `ty` Server Issues

**Files:**
- Modify: `python/helaicopter_api/application/gateway.py`
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/application/legacy-orchestration_orchestration.py`
- Modify: `python/helaicopter_api/ports/legacy-orchestration.py`
- Modify: `python/helaicopter_api/server/dependencies.py`
- Modify: `python/helaicopter_api/server/main.py`
- Modify: `tests/oats/test_legacy-orchestration_deployments.py`
- Test: `tests/test_api_bootstrap.py`
- Test: `tests/test_api_smoke.py`

- [ ] **Step 1: Reproduce the current hygiene failures with narrow commands**

Run:

```bash
uv run --group dev ruff check \
  python/helaicopter_api/application/gateway.py \
  python/helaicopter_api/application/orchestration.py \
  python/helaicopter_api/application/legacy-orchestration_orchestration.py \
  python/helaicopter_api/ports/legacy-orchestration.py \
  python/helaicopter_api/server/dependencies.py \
  python/helaicopter_api/server/main.py \
  tests/oats/test_legacy-orchestration_deployments.py

uv run --group dev ty check \
  python/helaicopter_api/ports/legacy-orchestration.py \
  python/helaicopter_api/server/dependencies.py \
  python/helaicopter_api/server/main.py \
  --error-on-warning
```

Expected: FAIL on unused imports, missing `RunRuntimeState`, partially unknown `tags`, stale `type: ignore` comments, and the FastAPI middleware typing mismatch.

- [ ] **Step 2: Make the minimal hygiene fixes**

Apply the straightforward cleanups:

```python
# python/helaicopter_api/application/gateway.py
- from typing import Any

# python/helaicopter_api/application/legacy-orchestration_orchestration.py
- legacy orchestrationDeploymentRecord,
- legacy orchestrationWorkPoolRecord,
- legacy orchestrationWorkerRecord,

# tests/oats/test_legacy-orchestration_deployments.py
- import pytest
```

And restore the missing runtime-state import:

```python
from oats.models import (
    AgentInvocationResult,
    InvocationRuntimeRecord,
    RunExecutionRecord,
    RunRuntimeState,
    TaskExecutionRecord,
    TaskRuntimeRecord,
)
```

- [ ] **Step 3: Fix the partially unknown `tags` list in the legacy orchestration port model**

Make the default factory explicit so `ty` sees a concrete `list[str]`:

```python
def _empty_tags() -> list[str]:
    return []

@dataclass(frozen=True, slots=True)
class legacy orchestrationDeploymentRecord:
    ...
    tags: list[str] = field(default_factory=_empty_tags)
```

- [ ] **Step 4: Remove the stale dependency suppressions**

Delete the two no-longer-needed ignores in `python/helaicopter_api/server/dependencies.py`:

```python
def get_settings(request: Request) -> Settings:
    return request.app.state.settings

def get_services(request: Request) -> BackendServices:
    return request.app.state.services
```

- [ ] **Step 5: Fix the middleware typing without changing runtime behavior**

Preserve the current middleware stack, but rewrite `create_app()` in the smallest way that `ty` accepts. Prefer a typed middleware list via `starlette.middleware.Middleware`; if `ty` still rejects that path, cast the middleware classes explicitly and keep the runtime smoke tests as the behavior guard.

The target shape is:

```python
from starlette.middleware import Middleware

middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    Middleware(GZipMiddleware, minimum_size=1000),
    Middleware(TimingMiddleware),
    Middleware(RequestIDMiddleware),
]

application = FastAPI(..., lifespan=lifespan, middleware=middleware)
```

- [ ] **Step 6: Run the focused tests and narrow analyzers**

Run:

```bash
uv run --group dev pytest -q tests/test_api_bootstrap.py tests/test_api_smoke.py
uv run --group dev ruff check \
  python/helaicopter_api/application/gateway.py \
  python/helaicopter_api/application/orchestration.py \
  python/helaicopter_api/application/legacy-orchestration_orchestration.py \
  python/helaicopter_api/ports/legacy-orchestration.py \
  python/helaicopter_api/server/dependencies.py \
  python/helaicopter_api/server/main.py \
  tests/oats/test_legacy-orchestration_deployments.py
uv run --group dev ty check \
  python/helaicopter_api/ports/legacy-orchestration.py \
  python/helaicopter_api/server/dependencies.py \
  python/helaicopter_api/server/main.py \
  --error-on-warning
```

Expected: PASS.

- [ ] **Step 7: Commit the hygiene and server-wiring cleanup**

```bash
git add python/helaicopter_api/application/gateway.py \
  python/helaicopter_api/application/orchestration.py \
  python/helaicopter_api/application/legacy-orchestration_orchestration.py \
  python/helaicopter_api/ports/legacy-orchestration.py \
  python/helaicopter_api/server/dependencies.py \
  python/helaicopter_api/server/main.py \
  tests/oats/test_legacy-orchestration_deployments.py
git commit -m "fix: clear initial ty and ruff blockers"
```

### Task 3: Fix Nominal-ID And Literal Narrowing Across API Adapters And Application Layers

**Files:**
- Modify: `python/helaicopter_api/adapters/app_sqlite/store.py`
- Modify: `python/helaicopter_api/adapters/claude_fs/conversations.py`
- Modify: `python/helaicopter_api/adapters/evaluation_jobs.py`
- Modify: `python/helaicopter_api/application/analytics.py`
- Modify: `python/helaicopter_api/application/conversations.py`
- Modify: `python/helaicopter_api/application/evaluation_prompts.py`
- Modify: `python/helaicopter_api/application/evaluations.py`
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/application/plans.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `python/helaicopter_api/pure/conversation_dag.py`
- Test: `tests/test_api_conversations.py`
- Test: `tests/test_api_evaluation_prompts.py`
- Test: `tests/test_api_evaluations.py`
- Test: `tests/test_api_orchestration.py`
- Test: `tests/test_api_plans.py`
- Test: `tests/test_api_analytics.py`

- [ ] **Step 1: Reproduce the adapter/application `ty` failures**

Run:

```bash
uv run --group dev ty check \
  python/helaicopter_api/adapters \
  python/helaicopter_api/application \
  python/helaicopter_api/bootstrap \
  python/helaicopter_api/pure \
  --output-format concise \
  --error-on-warning
```

Expected: FAIL with nominal-ID and literal diagnostics like `Expected PromptId, found str`, `Expected SessionId, found str`, unresolved union attributes on conversation blocks, and TypedDict key mismatches in plan-source payloads.

- [ ] **Step 2: Introduce explicit narrowing helpers instead of passing raw `str` through typed boundaries**

Create or reuse small local coercion helpers where application code crosses into `NewType` or `Literal` contracts:

```python
from helaicopter_domain.ids import AgentId, PlanId, PromptId, SessionId
from helaicopter_domain.vocab import ProviderName, RunRuntimeStatus, TaskRuntimeStatus

def _session_id(value: str) -> SessionId:
    return SessionId(value)

def _plan_id(value: str) -> PlanId:
    return PlanId(value)

def _provider_name(value: str) -> ProviderName:
    if value not in {"claude", "codex"}:
        raise ValueError(f"Unsupported provider: {value}")
    return value
```

Then replace call sites so functions expecting `SessionId`, `PromptId`, `PlanId`, `AgentId`, or provider/status literals are fed typed values instead of raw strings.

- [ ] **Step 3: Narrow heterogeneous payloads before attribute access**

Where `ty` reports unresolved attributes on conversation block unions or subprocess results, branch on the discriminant or use a typed protocol instead of treating the union as a monolith:

```python
match block.type:
    case "text":
        text = block.text
    case "thinking":
        text = block.thinking
    case "tool_call":
        tool_name = block.tool_name
        result = block.result
```

And for subprocess runners:

```python
from subprocess import CompletedProcess

result: CompletedProcess[str] = runner.run(...)
stdout = result.stdout
stderr = result.stderr
returncode = result.returncode
```

- [ ] **Step 4: Make the plan-source and Codex payload TypedDicts match real keys**

Update the local TypedDict definitions in `python/helaicopter_api/application/plans.py` and any Codex payload helpers so keys like `slug`, `projectPath`, `sessionId`, `eventId`, and `callId` are declared where the code actually reads them.

Example:

```python
class CodexSessionPlanSource(TypedDict, total=False):
    provider: Literal["codex"]
    sessionId: str
    eventId: str
    projectPath: str
    slug: str
```

- [ ] **Step 5: Verify the API behavior tests still pass**

Run:

```bash
uv run --group dev pytest -q \
  tests/test_api_conversations.py \
  tests/test_api_evaluation_prompts.py \
  tests/test_api_evaluations.py \
  tests/test_api_orchestration.py \
  tests/test_api_plans.py \
  tests/test_api_analytics.py
```

Expected: PASS.

- [ ] **Step 6: Re-run `ty` on the API cluster**

Run:

```bash
uv run --group dev ty check \
  python/helaicopter_api/adapters \
  python/helaicopter_api/application \
  python/helaicopter_api/bootstrap \
  python/helaicopter_api/pure \
  --output-format concise \
  --error-on-warning
```

Expected: PASS.

- [ ] **Step 7: Commit the API type-narrowing work**

```bash
git add python/helaicopter_api/adapters \
  python/helaicopter_api/application \
  python/helaicopter_api/bootstrap \
  python/helaicopter_api/pure
git commit -m "fix: narrow API types for ty"
```

### Task 4: Align Database TypedDict Payloads With Runtime Construction

**Files:**
- Modify: `python/helaicopter_api/application/database.py`
- Modify: `python/helaicopter_db/refresh.py`
- Modify: `python/helaicopter_db/status.py`
- Modify: `python/helaicopter_db/utils.py`
- Test: `tests/test_api_database.py`
- Test: `tests/test_backend_settings.py`
- Test: `tests/test_export_types.py`

- [ ] **Step 1: Reproduce the DB payload errors**

Run:

```bash
uv run --group dev ty check \
  python/helaicopter_api/application/database.py \
  python/helaicopter_db/refresh.py \
  python/helaicopter_db/status.py \
  python/helaicopter_db/utils.py \
  --output-format concise \
  --error-on-warning
```

Expected: FAIL on TypedDict key mismatches, `dict[str, object]` vs `DatabaseStatusPayload` mismatches, and raw `str` returns where `ConversationId`, `ToolId`, and similar `NewType`s are expected.

- [ ] **Step 2: Expand the TypedDict definitions to match the payloads the code already builds**

The runtime builders populate keys such as `health`, `operationalStatus`, `sizeBytes`, `sizeDisplay`, `inventorySummary`, and `load`. Make the TypedDicts in `python/helaicopter_db/status.py` reflect those keys rather than forcing the builders through incompatible shapes:

```python
class DatabaseArtifactPayload(TypedDict, total=False):
    key: str
    label: str
    engine: str
    role: str
    availability: str
    health: str | None
    operationalStatus: str | None
    sizeBytes: int | None
    sizeDisplay: str | None
    inventorySummary: str | None
    load: list[DatabaseLoadMetricPayload]
    tables: list[DatabaseTablePayload]
```

Keep the casing consistent with the actual payload boundary the builders use.

- [ ] **Step 3: Return nominal IDs explicitly from helper functions**

In `python/helaicopter_db/utils.py`, wrap string IDs in their declared `NewType`s:

```python
def conversation_id(provider: ProviderName, session_id: SessionId) -> ConversationId:
    return ConversationId(f"{provider}:{session_id}")

def tool_dim_id(provider: ProviderName, tool_name: str) -> ToolId:
    return ToolId(f"{provider}:{tool_name}")
```

Repeat that pattern for model, project, subagent, plan-row, and message-row helpers.

- [ ] **Step 4: Normalize status payload copying without erasing the TypedDict shape**

Avoid plain `dict(payload)` assignments that widen the type to `dict[Unknown, Unknown]`. Prefer typed copies or adapters:

```python
normalized: DatabaseStatusPayload = {
    **payload,
    "databases": _normalize_database_artifacts(payload["databases"]),
}
```

Use the existing `TypeAdapter` boundaries where they already exist instead of reintroducing anonymous dictionaries.

- [ ] **Step 5: Run the database tests**

Run:

```bash
uv run --group dev pytest -q \
  tests/test_api_database.py \
  tests/test_backend_settings.py \
  tests/test_export_types.py
```

Expected: PASS.

- [ ] **Step 6: Re-run `ty` on the DB cluster**

Run:

```bash
uv run --group dev ty check \
  python/helaicopter_api/application/database.py \
  python/helaicopter_db/refresh.py \
  python/helaicopter_db/status.py \
  python/helaicopter_db/utils.py \
  --output-format concise \
  --error-on-warning
```

Expected: PASS.

- [ ] **Step 7: Commit the DB payload alignment**

```bash
git add python/helaicopter_api/application/database.py \
  python/helaicopter_db/refresh.py \
  python/helaicopter_db/status.py \
  python/helaicopter_db/utils.py
git commit -m "fix: align database payload typing for ty"
```

### Task 5: Fix OATS Runtime And legacy orchestration Type Errors

**Files:**
- Modify: `python/oats/cli.py`
- Modify: `python/oats/parser.py`
- Modify: `python/oats/pr.py`
- Modify: `python/oats/legacy-orchestration/compiler.py`
- Modify: `python/oats/legacy-orchestration/flows.py`
- Modify: `python/oats/legacy-orchestration/tasks.py`
- Modify: `python/oats/runner.py`
- Test: `tests/test_cli_runtime.py`
- Test: `tests/test_runner.py`
- Test: `tests/oats/test_legacy-orchestration_compiler.py`
- Test: `tests/oats/test_legacy-orchestration_flows.py`
- Test: `tests/oats/test_legacy-orchestration_tasks.py`
- Test: `tests/oats/test_legacy-orchestration_worktree.py`

- [ ] **Step 1: Reproduce the OATS/legacy orchestration failures**

Run:

```bash
uv run --group dev ty check \
  python/oats \
  --output-format concise \
  --error-on-warning
```

Expected: FAIL on provider/status literals, `SessionId | None` narrowing, TypedDict keys in Codex runner events, `TextIO` vs `IO[str]`, and legacy orchestration overload typing.

- [ ] **Step 2: Reuse the domain literal types instead of passing generic `str`**

Where OATS runtime functions persist `RunRuntimeStatus`, `TaskRuntimeStatus`, `ProviderName`, or `TaskId`, validate/narrow before assignment:

```python
from helaicopter_domain.ids import TaskId
from helaicopter_domain.vocab import ProviderName, RunRuntimeStatus

task_id = TaskId(raw_task_id)
status: RunRuntimeStatus = "completed"
agent: ProviderName = "codex"
```

Update parser and CLI branches so impossible strings are rejected early rather than flowing into typed models.

- [ ] **Step 3: Fix the local TypedDicts in the runner to match the event stream**

Add the keys the code already reads:

```python
class _CodexThreadStartedEvent(TypedDict, total=False):
    item: _CodexAgentMessageItem

class _CodexItemCompletedEvent(TypedDict, total=False):
    thread_id: str
```

Then narrow `session_id` values before assigning them into `SessionId | None` fields.

- [ ] **Step 4: Resolve the legacy orchestration typing surfaces with explicit annotations or casts**

For overload issues in `python/oats/legacy-orchestration/flows.py` and possibly-missing submodule warnings in `python/oats/legacy-orchestration/tasks.py`, use the smallest annotation or import fix that preserves behavior:

```python
from legacy-orchestration.runtime import flow_run, task_run
```

and, if needed:

```python
from typing import cast

submitted = cast("legacy orchestrationFuture[CompiledTaskResult]", legacy-orchestration_compiled_task.submit(...))
```

- [ ] **Step 5: Fix `python/oats/runner.py` stream-handle annotations and writes**

Make the file-handle types match what `subprocess.Popen` and the local writer helpers actually accept. Preserve behavior and prefer explicit text-mode annotations over broad casts:

```python
from typing import TextIO, cast

stdout_handle = cast(TextIO | None, process.stdout)
stderr_handle = cast(TextIO | None, process.stderr)

if log_handle is not None:
    log_handle.write(chunk)
```

If a helper currently accepts `TextIO | None` but receives `IO[str] | None`, narrow the local variable before construction or widen the helper signature only when the callee truly supports any text stream.

- [ ] **Step 6: Run the OATS tests**

Run:

```bash
uv run --group dev pytest -q \
  tests/test_cli_runtime.py \
  tests/test_runner.py \
  tests/oats/test_legacy-orchestration_compiler.py \
  tests/oats/test_legacy-orchestration_flows.py \
  tests/oats/test_legacy-orchestration_tasks.py \
  tests/oats/test_legacy-orchestration_worktree.py
```

Expected: PASS.

- [ ] **Step 7: Re-run `ty` on `python/oats`**

Run: `uv run --group dev ty check python/oats --output-format concise --error-on-warning`

Expected: PASS.

- [ ] **Step 8: Commit the OATS typing cleanup**

```bash
git add python/oats
git commit -m "fix: make oats runtime ty-clean"
```

### Task 6: Full-Repo `ty` Burn-Down And Final Verification

**Files:**
- Modify: any remaining `python/**` file that still appears in the final `ty` output
- Test: `tests/`

- [ ] **Step 1: Run the full widened type-check command**

Run: `uv run --group dev ty check python --output-format concise --error-on-warning`

Expected: Either PASS or a much smaller residual list. If any files remain, fix them in place following the same patterns from Tasks 3-5:

- wrap `str` into `NewType` at typed boundaries
- narrow `Literal` values before assignment
- update local TypedDict definitions to match the payloads actually used
- branch on discriminated unions before accessing member-specific attributes

- [ ] **Step 2: Run the full lint and test suites**

Run:

```bash
uv run --group dev ruff check python tests
uv run --group dev pytest -q
uv run --group dev ty check python --error-on-warning
```

Expected:

- Ruff: `All checks passed!`
- pytest: full suite green
- ty: `All checks passed!`

- [ ] **Step 3: Inspect the final diff for stale pyright references in active contract files**

Run:

```bash
rg -n "pyright" \
  pyproject.toml \
  uv.lock \
  .github/workflows/backend-quality.yml \
  docs/python-backend-type-system-baseline.md \
  tests/test_backend_type_system_rollout.py \
  python \
  -S
```

Expected: no active contract references remain. Historical mentions inside old plans/specs may remain, but there should be no live config, workflow, baseline-doc, test-guardrail, or source dependency on `pyright`.

- [ ] **Step 4: Commit the final burn-down**

```bash
git add pyproject.toml .github/workflows/backend-quality.yml uv.lock docs tests python
git commit -m "fix: make ty the required python type checker"
```

- [ ] **Step 5: Record verification evidence for handoff**

Capture the final passing command set in the work summary:

```text
uv run --group dev ruff check python tests
uv run --group dev pytest -q
uv run --group dev ty check python --error-on-warning
```

Note any intentional deferrals explicitly. The only planned deferral from the spec is keeping `tests/**` outside required type checking.
