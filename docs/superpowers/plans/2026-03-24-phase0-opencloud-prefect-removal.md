# Phase 0: OpenCloud + Prefect Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all OpenCloud and Prefect code, routes, types, UI, docs, and tests from the codebase. The app supports three providers going forward: Claude Code, Codex, and OpenClaw.

**Architecture:** Systematic deletion working bottom-up — types/schemas first, then application logic, then UI, then docs. Each task targets a logical boundary (a module, a layer, or a feature area). Tests are updated alongside the code they cover.

**Tech Stack:** Python (FastAPI, Pydantic, SQLAlchemy), TypeScript (Next.js, Zod, React)

**Spec:** `docs/superpowers/specs/2026-03-24-mobile-interface-masterplan-design.md` (Phase 0 section)

---

## File Structure

### Files to DELETE entirely:
- `python/helaicopter_api/adapters/opencloud_sqlite/` (entire directory)
- `python/helaicopter_api/ports/opencloud_sqlite.py`
- `python/helaicopter_api/adapters/prefect_http.py`
- `python/helaicopter_api/ports/prefect.py`
- `python/helaicopter_api/router/prefect_orchestration.py`
- `python/helaicopter_api/application/prefect_orchestration.py`
- `python/helaicopter_api/schema/prefect_orchestration.py`
- `python/oats/prefect/` (entire directory)
- `src/components/orchestration/prefect-ui-embed.tsx`
- `src/lib/client/prefect-normalize.test.ts`
- `public/openapi/helaicopter-prefect-orchestration-api.json`
- `tests/oats/test_prefect_bootstrap_script.py`
- `tests/oats/test_prefect_compiler.py`
- `tests/oats/test_prefect_deployments.py`
- `tests/oats/test_prefect_flows.py`
- `tests/oats/test_prefect_ignore.py`
- `tests/oats/test_prefect_settings.py`
- `tests/oats/test_prefect_tasks.py`
- `tests/oats/test_prefect_worktree.py`
- `tests/test_api_prefect_orchestration.py`
- `docs/prefect-local-ops.md`
- `docs/oats-prefect-cutover.md`
- `docs/orchestration/prefect.mdx`
- `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`
- `docs/superpowers/plans/2026-03-19-full-program-oats-prefect-pipeline.md`
- `docs/superpowers/plans/2026-03-22-opencloud-opencode-provider.md`
- `docs/superpowers/specs/2026-03-18-prefect-native-oats-orchestration-design.md`
- `docs/superpowers/specs/2026-03-19-full-program-oats-prefect-overnight-run-design.md`
- `docs/superpowers/specs/2026-03-22-opencloud-opencode-provider-design.md`
- `examples/prefect_native_oats_orchestration_run.md`

### Files to MODIFY:
- `python/helaicopter_semantics/models.py`
- `python/helaicopter_domain/vocab.py`
- `python/helaicopter_api/bootstrap/services.py`
- `python/helaicopter_api/server/config.py`
- `python/helaicopter_api/server/openapi_artifacts.py`
- `python/helaicopter_api/router/router.py`
- `python/helaicopter_api/application/conversation_refs.py`
- `python/helaicopter_api/application/conversations.py`
- `python/helaicopter_api/application/orchestration.py`
- `python/helaicopter_api/application/gateway.py`
- `python/helaicopter_api/application/database.py`
- `python/helaicopter_db/orchestration_facts.py`
- `python/helaicopter_db/status.py`
- `python/helaicopter_db/utils.py`
- `python/oats/cli.py`
- `pyproject.toml`
- `src/lib/types.ts`
- `src/lib/routes.ts`
- `src/lib/client/endpoints.ts`
- `src/lib/client/normalize.ts`
- `src/lib/client/schemas/shared.ts`
- `src/lib/client/schemas/runtime.ts`
- `src/lib/client/schemas/database.ts`
- `src/components/ui/provider-filter.tsx`
- `src/components/conversation/conversation-viewer.tsx`
- `src/components/conversation/conversation-list.tsx`
- `src/components/analytics/cost-breakdown-card.tsx`
- `src/views/plans/plans-index-view.tsx`
- `src/features/plans/components/plan-panel.tsx`
- `src/components/orchestration/orchestration-hub.tsx`
- `src/components/databases/database-dashboard.tsx`
- `src/app/orchestration/page.tsx`

### Test files to MODIFY:
- `tests/test_semantics.py`
- `tests/test_api_conversations.py`
- `tests/test_api_analytics.py`
- `tests/test_backend_settings.py`
- `tests/test_api_bootstrap.py`
- `tests/test_api_database.py`
- `tests/test_api_orchestration.py`
- `tests/test_orchestration_analytics.py`
- `src/app/conversations/[...segments]/page.test.ts`
- `src/lib/client/normalize.test.ts`
- `src/lib/client/mutations.test.ts`
- `src/lib/client/schemas/shared.test.ts`
- `src/lib/routes.test.ts`
- `src/components/orchestration/tabs.test.ts`

---

## Task 1: Remove OpenCloud from Python type system

**Files:**
- Modify: `python/helaicopter_semantics/models.py`
- Modify: `python/helaicopter_domain/vocab.py`
- Modify: `python/helaicopter_api/application/conversation_refs.py`
- Modify: `python/helaicopter_db/utils.py`
- Modify: `tests/test_semantics.py`

- [ ] **Step 1: Update ProviderIdentifier in models.py**

In `python/helaicopter_semantics/models.py`, line 11:
```python
# FROM:
ProviderIdentifier = Literal["claude", "codex", "openclaw", "opencloud"]
# TO:
ProviderIdentifier = Literal["claude", "codex", "openclaw"]
```

Also remove `"opencloud"` from the set on line 39:
```python
# FROM:
if provider_lower in {"codex", "openclaw", "opencloud"}:
# TO:
if provider_lower in {"codex", "openclaw"}:
```

Delete the opencloud project_path prefix check (lines 44-45):
```python
# DELETE these two lines:
if project_path.startswith("opencloud:"):
    return "opencloud"
```

- [ ] **Step 2: Update vocab.py types**

In `python/helaicopter_domain/vocab.py`:
```python
# Line 5 FROM:
ProviderName = Literal["claude", "codex", "openclaw", "opencloud"]
# TO:
ProviderName = Literal["claude", "codex", "openclaw"]

# Line 6 FROM:
ProviderSelection = Literal["all", "claude", "codex", "openclaw", "opencloud"]
# TO:
ProviderSelection = Literal["all", "claude", "codex", "openclaw"]
```

- [ ] **Step 3: Update conversation_refs.py**

In `python/helaicopter_api/application/conversation_refs.py`, line 10:
```python
# FROM:
_KNOWN_CONVERSATION_REF_PROVIDERS = ("claude", "codex", "openclaw", "opencloud")
# TO:
_KNOWN_CONVERSATION_REF_PROVIDERS = ("claude", "codex", "openclaw")
```

- [ ] **Step 4: Update utils.py**

In `python/helaicopter_db/utils.py`, delete lines 41-42:
```python
# DELETE these two lines:
if project_path.startswith("opencloud:"):
    return "opencloud"
```

- [ ] **Step 5: Remove OpenCloud tests from test_semantics.py**

In `tests/test_semantics.py`, delete the test functions:
- `test_explicit_opencloud_provider_field_takes_precedence`
- `test_opencloud_project_path_prefix_identifies_opencloud`

- [ ] **Step 6: Run Python tests**

Run: `cd /Users/tony/Code/helaicopter-main && python -m pytest tests/test_semantics.py -v`
Expected: All remaining tests pass. OpenCloud tests are gone.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove opencloud from python type system"
```

---

## Task 2: Delete OpenCloud adapter and port modules

**Files:**
- Delete: `python/helaicopter_api/adapters/opencloud_sqlite/` (entire directory)
- Delete: `python/helaicopter_api/ports/opencloud_sqlite.py`

- [ ] **Step 1: Delete the opencloud_sqlite adapter directory**

```bash
rm -rf python/helaicopter_api/adapters/opencloud_sqlite/
```

- [ ] **Step 2: Delete the opencloud_sqlite port**

```bash
rm python/helaicopter_api/ports/opencloud_sqlite.py
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: delete opencloud adapter and port modules"
```

---

## Task 3: Remove OpenCloud from bootstrap and config

**Files:**
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `python/helaicopter_api/server/config.py`
- Modify: `tests/test_backend_settings.py`
- Modify: `tests/test_api_bootstrap.py`

- [ ] **Step 1: Remove OpenCloud from services.py**

In `python/helaicopter_api/bootstrap/services.py`:
- Delete line 30: `from ..adapters.opencloud_sqlite import FileOpenCloudStore`
- Delete line 38: `from ..ports.opencloud_sqlite import OpenCloudStore`
- Delete field line 134: `opencloud_store: OpenCloudStore`
- Delete cache key line 150: `"opencloud_sessions",`
- Delete instantiation line 225: `opencloud_store = FileOpenCloudStore(db_path=settings.opencloud_sqlite_path)`
- Delete parameter line 243: `opencloud_store=opencloud_store,`

- [ ] **Step 2: Remove OpenCloud from config.py**

In `python/helaicopter_api/server/config.py`:
- Delete `opencloud_dir: Path` field from CliSettings (line 51)
- Delete `opencloud_sqlite_path` property from CliSettings (lines 94-96)
- Delete `opencloud_dir` Field from Settings (lines 180-183)
- Delete `opencloud_dir=self.opencloud_dir` from cli property (line 200)
- Delete `opencloud_sqlite_path` property from Settings (lines 304-306)

- [ ] **Step 3: Update tests**

In `tests/test_backend_settings.py`: Remove any assertions about `opencloud_dir` or `opencloud_sqlite_path`.
In `tests/test_api_bootstrap.py`: Remove any OpenCloud store references.

- [ ] **Step 4: Run tests**

Run: `cd /Users/tony/Code/helaicopter-main && python -m pytest tests/test_backend_settings.py tests/test_api_bootstrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove opencloud from bootstrap and config"
```

---

## Task 4: Remove OpenCloud from conversations.py

**Files:**
- Modify: `python/helaicopter_api/application/conversations.py`
- Modify: `tests/test_api_conversations.py`

- [ ] **Step 1: Remove OpenCloud imports from conversations.py**

Remove any imports referencing OpenCloud types (OpenCloudSessionRecord, OpenCloudMessageRecord, OpenCloudPartRecord, etc.) from the top of the file.

- [ ] **Step 2: Remove OpenCloud function definitions**

Delete all functions with "opencloud" in their name:
- `_resolve_live_opencloud_conversation_identity`
- `_list_opencloud_live_summaries`
- `_summarize_opencloud_session`
- `_get_opencloud_live_conversation`
- `_opencloud_sessions`
- `_opencloud_parts_by_message`
- `_opencloud_user_texts`
- `_first_opencloud_user_message`
- `_opencloud_usage_for_message`
- `_opencloud_project_path`

- [ ] **Step 3: Remove OpenCloud call sites**

Search for all remaining references to "opencloud" in conversations.py — these will be call sites in dispatcher/routing functions. Remove the `provider == "opencloud"` branches and their calls to the deleted functions.

Also remove the `opencloud:` project path prefix check (around line 3912-3913).

- [ ] **Step 4: Remove OpenCloud from conversations tests**

In `tests/test_api_conversations.py`: Remove test data and test cases that reference OpenCloud.

- [ ] **Step 5: Run tests**

Run: `cd /Users/tony/Code/helaicopter-main && python -m pytest tests/test_api_conversations.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove opencloud from conversation application logic"
```

---

## Task 5: Remove OpenCloud from TypeScript types and schemas

**Files:**
- Modify: `src/lib/types.ts`
- Modify: `src/lib/client/schemas/shared.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/normalize.test.ts`
- Modify: `src/lib/client/schemas/shared.test.ts`

- [ ] **Step 1: Update FrontendProvider type**

In `src/lib/types.ts`, line 534:
```typescript
// FROM:
export type FrontendProvider = "claude" | "codex" | "openclaw" | "opencloud";
// TO:
export type FrontendProvider = "claude" | "codex" | "openclaw";
```

- [ ] **Step 2: Remove opencloud fields from types.ts**

Remove `opencloud?: number` from `ProviderBreakdown` interface (line 768).
Delete all `opencloud*` fields from `AnalyticsTimeSeriesPoint` (lines 834-845).
Delete all `opencloud*` fields from `DailyUsage` (lines 930-935).

- [ ] **Step 3: Update shared schema**

In `src/lib/client/schemas/shared.ts`, line 31:
```typescript
// FROM:
export const providers = ["claude", "codex", "openclaw", "opencloud"] as const;
// TO:
export const providers = ["claude", "codex", "openclaw"] as const;
```

- [ ] **Step 4: Remove opencloud from normalize.ts**

In `src/lib/client/normalize.ts`: Delete all lines mapping `opencloud` or `opencloud*` fields (lines ~737, 783-784, 851-879, 964-979).

- [ ] **Step 5: Update tests**

In `src/lib/client/normalize.test.ts`: Remove OpenCloud test data (line ~420 and any other references).
In `src/lib/client/schemas/shared.test.ts`: Remove OpenCloud schema validation tests.

- [ ] **Step 6: Run TypeScript build check**

Run: `cd /Users/tony/Code/helaicopter-main && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove opencloud from typescript types and schemas"
```

---

## Task 6: Remove OpenCloud from UI components

**Files:**
- Modify: `src/components/ui/provider-filter.tsx`
- Modify: `src/components/conversation/conversation-viewer.tsx`
- Modify: `src/components/conversation/conversation-list.tsx`
- Modify: `src/components/analytics/cost-breakdown-card.tsx`
- Modify: `src/views/plans/plans-index-view.tsx`
- Modify: `src/features/plans/components/plan-panel.tsx`
- Modify: `src/app/conversations/[...segments]/page.test.ts`

- [ ] **Step 1: Remove from provider-filter.tsx**

Delete line 13: `{ value: "opencloud", label: "OpenCloud" },`

- [ ] **Step 2: Remove from conversation-viewer.tsx**

Delete the line: `if (projectPath.startsWith("opencloud:")) return "opencloud";`

- [ ] **Step 3: Remove from conversation-list.tsx**

Delete the line: `if (projectPath.startsWith("opencloud:")) return "opencloud";`

- [ ] **Step 4: Remove from cost-breakdown-card.tsx**

Delete the line: `if (provider === "opencloud") return "OpenCloud";`

- [ ] **Step 5: Remove from plans views**

In `src/views/plans/plans-index-view.tsx` and `src/features/plans/components/plan-panel.tsx`: Remove the `"OpenCloud"` case from the provider name mapping function. If it's the last else-if before a default, simplify the logic.

- [ ] **Step 6: Update conversation page tests**

In `src/app/conversations/[...segments]/page.test.ts`: Remove OpenCloud test cases (lines ~460-487, 529).

- [ ] **Step 7: Run build**

Run: `cd /Users/tony/Code/helaicopter-main && npm run build`
Expected: Build succeeds

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: remove opencloud from ui components"
```

---

## Task 7: Delete OpenCloud documentation

**Files:**
- Delete: `docs/superpowers/plans/2026-03-22-opencloud-opencode-provider.md`
- Delete: `docs/superpowers/specs/2026-03-22-opencloud-opencode-provider-design.md`
- Modify: `docs/superpowers/specs/2026-03-22-openclaw-conversation-tabs-design.md` (remove opencloud references)

- [ ] **Step 1: Delete OpenCloud docs**

```bash
rm docs/superpowers/plans/2026-03-22-opencloud-opencode-provider.md
rm docs/superpowers/specs/2026-03-22-opencloud-opencode-provider-design.md
```

- [ ] **Step 2: Clean OpenCloud references from remaining docs**

In `docs/superpowers/specs/2026-03-22-openclaw-conversation-tabs-design.md`: Remove or update any mentions of OpenCloud.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: remove opencloud documentation"
```

---

## Task 8: Delete Prefect Python modules

**Files:**
- Delete: `python/oats/prefect/` (entire directory)
- Delete: `python/helaicopter_api/adapters/prefect_http.py`
- Delete: `python/helaicopter_api/ports/prefect.py`
- Delete: `python/helaicopter_api/router/prefect_orchestration.py`
- Delete: `python/helaicopter_api/application/prefect_orchestration.py`
- Delete: `python/helaicopter_api/schema/prefect_orchestration.py`
- Delete: All `tests/oats/test_prefect_*.py` files
- Delete: `tests/test_api_prefect_orchestration.py`

- [ ] **Step 1: Delete the oats/prefect directory**

```bash
rm -rf python/oats/prefect/
```

- [ ] **Step 2: Delete Prefect API modules**

```bash
rm python/helaicopter_api/adapters/prefect_http.py
rm python/helaicopter_api/ports/prefect.py
rm python/helaicopter_api/router/prefect_orchestration.py
rm python/helaicopter_api/application/prefect_orchestration.py
rm python/helaicopter_api/schema/prefect_orchestration.py
```

- [ ] **Step 3: Delete Prefect test files**

```bash
rm tests/oats/test_prefect_*.py
rm tests/test_api_prefect_orchestration.py
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: delete prefect python modules and tests"
```

---

## Task 9: Remove Prefect from Python wiring (bootstrap, config, router)

**Files:**
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `python/helaicopter_api/server/config.py`
- Modify: `python/helaicopter_api/router/router.py`
- Modify: `python/helaicopter_api/server/openapi_artifacts.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Remove Prefect from router.py**

In `python/helaicopter_api/router/router.py`:
- Delete import line 18: `from .prefect_orchestration import prefect_orchestration_router`
- Delete include line ~43: `root_router.include_router(prefect_orchestration_router)`

- [ ] **Step 2: Remove Prefect from services.py**

In `python/helaicopter_api/bootstrap/services.py`:
- Delete line 31: `from ..adapters.prefect_http import PrefectHttpAdapter`
- Delete line 40: `from ..ports.prefect import PrefectOrchestrationPort`
- Delete field line 137: `prefect_client: PrefectOrchestrationPort`
- Delete instantiation line 225: `prefect_client = PrefectHttpAdapter.from_settings(settings.prefect)`
- Delete parameter line 245: `prefect_client=prefect_client,`

- [ ] **Step 3: Remove Prefect from config.py**

In `python/helaicopter_api/server/config.py`:
- Delete entire `PrefectApiSettings` class (lines ~138-143)
- Delete `prefect_api_url` field (lines ~194-197)
- Delete `prefect_api_timeout_seconds` field (lines ~198-201)
- Delete `prefect` cached_property (lines ~240-244)

- [ ] **Step 4: Remove Prefect from openapi_artifacts.py**

In `python/helaicopter_api/server/openapi_artifacts.py`: Delete the Prefect OpenAPI artifact generation block (lines ~115-125).

- [ ] **Step 5: Remove Prefect from pyproject.toml**

Delete the `prefect>=3.0.0` dependency line.

- [ ] **Step 6: Run Python import check**

Run: `cd /Users/tony/Code/helaicopter-main && python -c "from helaicopter_api.server.main import create_app; print('OK')"`
Expected: OK (app loads without import errors)

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove prefect from bootstrap, config, and router wiring"
```

---

## Task 10: Remove Prefect from application logic

**Files:**
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/application/gateway.py`
- Modify: `python/helaicopter_api/application/database.py`
- Modify: `python/helaicopter_db/orchestration_facts.py`
- Modify: `python/helaicopter_db/status.py`
- Modify: `python/helaicopter_domain/vocab.py`
- Modify: `python/oats/cli.py`
- Modify: `tests/test_api_orchestration.py`
- Modify: `tests/test_orchestration_analytics.py`
- Modify: `tests/test_api_database.py`
- Modify: `tests/test_api_bootstrap.py`

- [ ] **Step 1: Remove Prefect from orchestration.py**

In `python/helaicopter_api/application/orchestration.py`:
- Delete line ~53: `from oats.prefect.analytics import StoredLocalFlowRunArtifacts, load_local_flow_run_artifacts`
- Delete lines ~57-59: `_PREFECT_ACTIVE_STATES`, `_PREFECT_PENDING_STATES`, `_PREFECT_FAILED_STATES` constants
- Delete `_prefect_flow_runs_by_id` function (lines ~292-297)
- Delete `_prefect_attempts_by_task_id` function (lines ~487-496)
- Delete Prefect status normalization functions
- Remove all `mode="prefect"` branches and `prefect_artifacts`/`prefect_attempt` handling
- Remove `prefect_flow_run` and `prefect_artifacts` parameters from function signatures where they appear

- [ ] **Step 2: Remove Prefect from gateway.py**

In `python/helaicopter_api/application/gateway.py`: Delete the Prefect `GatewaySurfaceResponse` block (lines ~59-68).

- [ ] **Step 3: Remove Prefect from database.py**

In `python/helaicopter_api/application/database.py`: Remove `prefectPostgres` check and database config (lines ~183, 274-285).

- [ ] **Step 4: Remove Prefect from orchestration_facts.py**

In `python/helaicopter_db/orchestration_facts.py`:
- Delete line ~18: `from oats.prefect.analytics import StoredLocalFlowRunArtifacts, load_local_flow_run_artifacts`
- Delete Prefect artifact loading functions and fact building functions (`_build_prefect_run_fact`, `_build_prefect_task_attempt_facts`, etc.)

- [ ] **Step 5: Remove Prefect from status.py**

In `python/helaicopter_db/status.py`:
- Delete line 63: `prefectPostgres: DatabaseArtifactPayload`
- Delete `_prefect_postgres_target` function (lines ~112-119)
- Delete `prefectPostgres` configuration block (lines ~397-408)

- [ ] **Step 6: Update vocab.py**

In `python/helaicopter_domain/vocab.py`, line ~12:
```python
# FROM:
DatabaseStatusKey = Literal["frontend_cache", "sqlite", "duckdb", "prefect_postgres"]
# TO:
DatabaseStatusKey = Literal["frontend_cache", "sqlite", "duckdb"]
```

- [ ] **Step 7: Remove Prefect from oats CLI**

In `python/oats/cli.py`:
- Delete Prefect imports (lines ~22-27): `PrefectApiError`, `deploy_run_spec`, `read_flow_run_status`, `trigger_run_spec`
- Delete `prefect_app` Typer instance (line ~87) and `app.add_typer(prefect_app, name="prefect")` (line ~88)
- Update help text on line ~83 to remove "prefect deploy, run, status" mention
- Delete all `@prefect_app.command()` decorated functions at the bottom of the file

- [ ] **Step 8: Update orchestration and database tests**

In `tests/test_api_orchestration.py`: Remove Prefect references.
In `tests/test_orchestration_analytics.py`: Remove Prefect references.
In `tests/test_api_database.py`: Remove `prefectPostgres` references.
In `tests/test_api_bootstrap.py`: Remove Prefect client references.

- [ ] **Step 9: Run tests**

Run: `cd /Users/tony/Code/helaicopter-main && python -m pytest tests/test_api_orchestration.py tests/test_orchestration_analytics.py tests/test_api_database.py tests/test_api_bootstrap.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: remove prefect from application logic, database, and oats cli"
```

---

## Task 11: Remove Prefect from TypeScript frontend

**Files:**
- Modify: `src/lib/types.ts`
- Modify: `src/lib/routes.ts`
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/client/schemas/runtime.ts`
- Modify: `src/lib/client/schemas/database.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/normalize.test.ts`
- Modify: `src/lib/client/mutations.test.ts`
- Modify: `src/lib/routes.test.ts`
- Delete: `src/lib/client/prefect-normalize.test.ts`

- [ ] **Step 1: Update runtime schema**

In `src/lib/client/schemas/runtime.ts`:
- Remove `"prefect-ui"` from `orchestrationTabs` array (line ~33)
- Delete `prefectPathSchema` (lines ~45-55)
- Delete `parsePrefectPath` function (lines ~66-69)

- [ ] **Step 2: Update database schema**

In `src/lib/client/schemas/database.ts`:
- Remove `"prefect_postgres"` from `databaseStatusKeySchema` enum (line ~12)

- [ ] **Step 3: Update types.ts**

In `src/lib/types.ts`:
- Remove `"prefect_postgres"` from `DatabaseStatusKey` type (if it's a manual type mirroring the schema)
- Remove `prefectPostgres` field from database status types

- [ ] **Step 4: Remove Prefect endpoints**

In `src/lib/client/endpoints.ts`: Delete all `orchestrationPrefect*` functions (lines ~197-219 — `orchestrationPrefectDeployments`, `orchestrationPrefectDeployment`, `orchestrationPrefectFlowRuns`, `orchestrationPrefectFlowRun`, `orchestrationPrefectWorkers`, `orchestrationPrefectWorkPools`).

- [ ] **Step 5: Update routes.ts**

In `src/lib/routes.ts`:
- Delete `parsePrefectPath` from imports (line ~4)
- Delete `PREFECT_UI_URL` constant (line ~77)
- Delete `normalizePrefectUiPath` function (lines ~104-106)
- Delete `buildPrefectUiUrl` function (lines ~108-111)
- Remove `prefectPath` from `buildOrchestrationRoute` opts type and logic (lines ~595, 604-607)
- Remove `prefectPath` from `getOrchestrationRouteState` types, logic, and return (lines ~617, 622, 624-626, 632)

- [ ] **Step 6: Update normalize.ts**

In `src/lib/client/normalize.ts` and `src/lib/client/normalize.test.ts`: Remove Prefect test data references (lines ~1289-2011 in test file).

- [ ] **Step 7: Delete prefect-normalize test**

```bash
rm src/lib/client/prefect-normalize.test.ts
```

- [ ] **Step 8: Update remaining test files**

In `src/lib/client/mutations.test.ts`: Remove Prefect database status tests.
In `src/lib/routes.test.ts`: Remove Prefect route tests (lines ~393-450).
In `src/lib/client/schemas/shared.test.ts`: Remove Prefect schema tests.

- [ ] **Step 9: Run TypeScript build**

Run: `cd /Users/tony/Code/helaicopter-main && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: remove prefect from typescript types, schemas, routes, and endpoints"
```

---

## Task 12: Remove Prefect from UI components

**Files:**
- Modify: `src/components/orchestration/orchestration-hub.tsx`
- Delete: `src/components/orchestration/prefect-ui-embed.tsx`
- Modify: `src/components/databases/database-dashboard.tsx`
- Modify: `src/app/orchestration/page.tsx`
- Modify: `src/components/orchestration/tabs.test.ts`
- Delete: `public/openapi/helaicopter-prefect-orchestration-api.json`

- [ ] **Step 1: Update orchestration-hub.tsx**

In `src/components/orchestration/orchestration-hub.tsx`:
- Delete import line 6: `import { PrefectUiEmbed } from "./prefect-ui-embed";`
- Remove `prefectPath` from props (lines ~12, 15)
- Delete `<TabsTrigger value="prefect-ui">Prefect UI</TabsTrigger>` (line ~28)
- Delete `<TabsContent value="prefect-ui">...</TabsContent>` block (lines ~42-44)

- [ ] **Step 2: Delete prefect-ui-embed.tsx**

```bash
rm src/components/orchestration/prefect-ui-embed.tsx
```

- [ ] **Step 3: Update orchestration page**

In `src/app/orchestration/page.tsx`:
- Remove `prefectPath` from searchParams type (line ~7)
- Remove `prefectPath` from destructuring (line ~9)
- Remove `prefectPath={prefectPath}` prop (line ~15)

- [ ] **Step 4: Update database-dashboard.tsx**

In `src/components/databases/database-dashboard.tsx`: Remove the `prefectPostgres` display section (lines ~295-358).

- [ ] **Step 5: Update tabs test**

In `src/components/orchestration/tabs.test.ts`: Remove Prefect UI tab test (lines ~10-13).

- [ ] **Step 6: Delete Prefect OpenAPI artifact**

```bash
rm public/openapi/helaicopter-prefect-orchestration-api.json
```

- [ ] **Step 7: Run build**

Run: `cd /Users/tony/Code/helaicopter-main && npm run build`
Expected: Build succeeds

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: remove prefect from ui components and openapi artifacts"
```

---

## Task 13: Delete Prefect documentation

**Files:**
- Delete: `docs/prefect-local-ops.md`
- Delete: `docs/oats-prefect-cutover.md`
- Delete: `docs/orchestration/prefect.mdx`
- Delete: `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`
- Delete: `docs/superpowers/plans/2026-03-19-full-program-oats-prefect-pipeline.md`
- Delete: `docs/superpowers/specs/2026-03-18-prefect-native-oats-orchestration-design.md`
- Delete: `docs/superpowers/specs/2026-03-19-full-program-oats-prefect-overnight-run-design.md`
- Delete: `examples/prefect_native_oats_orchestration_run.md`
- Modify: remaining docs with Prefect references

- [ ] **Step 1: Delete Prefect doc files**

```bash
rm docs/prefect-local-ops.md
rm docs/oats-prefect-cutover.md
rm docs/orchestration/prefect.mdx
rm docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md
rm docs/superpowers/plans/2026-03-19-full-program-oats-prefect-pipeline.md
rm docs/superpowers/specs/2026-03-18-prefect-native-oats-orchestration-design.md
rm docs/superpowers/specs/2026-03-19-full-program-oats-prefect-overnight-run-design.md
rm examples/prefect_native_oats_orchestration_run.md
```

- [ ] **Step 2: Clean Prefect references from remaining docs**

Search all remaining docs for "prefect" and remove or update references:
- `docs/guides/orchestration.mdx`
- `docs/orchestration/oats.mdx`
- `docs/orchestration/overview.mdx`
- `docs/mint.json` (remove Prefect nav entries)
- `docs/routes-and-data-model-audit.md`
- `docs/fastapi-backend-rollout.md`
- Other specs/plans that mention Prefect in passing
- `examples/full_program_authoritative_analytics_overnight_run.md`
- `examples/cleanup.md`

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: remove prefect documentation"
```

---

## Task 14: Regenerate OpenAPI artifacts and final verification

**Files:**
- Regenerate: `public/openapi/*.json`

- [ ] **Step 1: Regenerate OpenAPI artifacts**

Run: `cd /Users/tony/Code/helaicopter-main && npm run api:openapi`
Expected: Artifacts regenerated without Prefect endpoints

- [ ] **Step 2: Verify no remaining references**

Run:
```bash
grep -ri "opencloud" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.mdx" --include="*.md" python/ src/ tests/ docs/ examples/ | grep -v node_modules | grep -v .next | grep -v "mobile-interface-masterplan" | grep -v "phase0-opencloud-prefect-removal"
```
Expected: No matches (or only the design spec itself)

```bash
grep -ri "prefect" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.mdx" --include="*.md" python/ src/ tests/ docs/ examples/ | grep -v node_modules | grep -v .next | grep -v "mobile-interface-masterplan" | grep -v "phase0-opencloud-prefect-removal"
```
Expected: No matches (or only the design spec itself)

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/tony/Code/helaicopter-main && python -m pytest -x -v`
Expected: All tests pass

Run: `cd /Users/tony/Code/helaicopter-main && npm run build`
Expected: Build succeeds

Run: `cd /Users/tony/Code/helaicopter-main && npm run lint`
Expected: No lint errors

- [ ] **Step 4: Commit OpenAPI artifacts**

```bash
git add -A
git commit -m "chore: regenerate openapi artifacts after opencloud and prefect removal"
```

- [ ] **Step 5: Verify FastAPI starts**

Run: `cd /Users/tony/Code/helaicopter-main && timeout 10 npm run api:dev || true`
Expected: Server starts without import errors (will timeout after 10s, that's fine)
