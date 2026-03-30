# Remove Repo-Local Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all repo-local orchestration responsibilities from Helaicopter, including the packaged OATS runtime, orchestration/dispatch/workers backend APIs, and the corresponding frontend UI.

**Architecture:** First sever the live product surface by removing router registration, page routing, and client entry points. Then remove the now-unreferenced orchestration runtime, schemas, adapters, and tests. Finish by updating docs and verification so the remaining app describes only the supported product surface.

**Tech Stack:** Next.js 16, React 19, TypeScript, FastAPI, Python 3.13, `pytest`, `node:test`, ESLint

---

## File Structure

**Frontend routes and UI:**
- Delete: `src/app/orchestration/page.tsx`
- Delete: `src/components/orchestration/*`
- Delete: `src/components/dispatch/queue-monitor.tsx`
- Delete: `src/components/workers/*`
- Modify: `src/app/page.tsx`
- Modify: `src/app/layout.tsx`
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/client/mutations.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/normalize.test.ts`
- Delete: `src/lib/client/dispatch.ts`
- Delete: `src/lib/client/workers.ts`
- Delete: `src/lib/client/schemas/dispatch.ts`
- Modify: `src/lib/client/schemas/runtime.ts`
- Modify: `src/lib/client/schemas/shared.ts`
- Modify: `src/lib/client/schemas/shared.test.ts`
- Modify: `src/lib/types.ts`
- Modify: frontend tests that reference orchestration tabs or removed models

**Backend orchestration/control plane:**
- Delete: `python/helaicopter_api/router/orchestration.py`
- Delete: `python/helaicopter_api/router/dispatch.py`
- Delete: `python/helaicopter_api/router/workers.py`
- Modify: `python/helaicopter_api/router/router.py`
- Delete: `python/helaicopter_api/application/orchestration.py`
- Delete: `python/helaicopter_api/application/oats_run_actions.py`
- Delete: `python/helaicopter_api/application/dispatch.py`
- Delete: `python/helaicopter_api/application/dispatch_monitor.py`
- Delete: `python/helaicopter_api/application/workers.py`
- Delete: `python/helaicopter_api/application/worker_state.py`
- Delete: `python/helaicopter_api/application/resolver.py`
- Delete: `python/helaicopter_api/schema/orchestration.py`
- Delete: `python/helaicopter_api/schema/dispatch.py`
- Delete: `python/helaicopter_api/schema/workers.py`
- Delete: `python/helaicopter_api/ports/orchestration.py`
- Delete: `python/helaicopter_api/adapters/oats_artifacts/*`
- Modify: `python/helaicopter_api/adapters/__init__.py`
- Modify: `python/helaicopter_api/ports/__init__.py`
- Modify: `python/helaicopter_api/schema/__init__.py`
- Modify: `python/helaicopter_api/server/lifespan.py`
- Modify: `python/helaicopter_api/server/openapi.py`
- Modify: `python/helaicopter_api/server/openapi_artifacts.py`
- Modify: `python/helaicopter_api/server/config.py`
- Modify: `python/helaicopter_api/application/gateway.py`

**Packaged runtime and docs:**
- Delete: `python/oats/*`
- Modify: `pyproject.toml`
- Modify: `package.json`
- Modify: `README.md`
- Delete or update examples/docs that only reference OATS orchestration

**Tests:**
- Delete: `tests/oats/*`
- Delete: `tests/test_api_dispatch.py`
- Delete: `tests/test_api_workers.py`
- Delete: `tests/test_repo_config.py`
- Delete: `tests/test_resolver_loop.py`
- Modify: `tests/test_backend_settings.py`
- Modify: any backend/frontend tests that still import orchestration models

## Task 1: Remove the live frontend orchestration surface

**Files:**
- Delete: `src/app/orchestration/page.tsx`
- Delete: `src/components/orchestration/*`
- Delete: `src/components/dispatch/queue-monitor.tsx`
- Delete: `src/components/workers/*`
- Modify: `src/app/page.tsx`
- Modify: `src/app/layout.tsx`
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/client/mutations.ts`
- Delete: `src/lib/client/dispatch.ts`
- Delete: `src/lib/client/workers.ts`
- Delete: frontend-only orchestration tests

- [ ] **Step 1: Write failing frontend tests for the remaining runtime navigation without orchestration**

Write or update a small test that asserts the shared runtime tab parsing and top-level navigation no longer accept or render `orchestration`.

- [ ] **Step 2: Run the targeted frontend test and confirm it fails**

Run: `node --test src/lib/client/schemas/shared.test.ts`

- [ ] **Step 3: Remove the route, components, and client entry points**

Delete the orchestration page and all orchestration/dispatch/workers UI. Remove any homepage or layout links/cards that point to orchestration. Remove now-dead client endpoints and mutations.

- [ ] **Step 4: Re-run the targeted frontend test and confirm it passes**

Run: `node --test src/lib/client/schemas/shared.test.ts`

- [ ] **Step 5: Commit**

```bash
git add src
git commit -m "refactor: remove orchestration frontend surfaces"
```

## Task 2: Remove backend orchestration, dispatch, and workers

**Files:**
- Delete: `python/helaicopter_api/router/orchestration.py`
- Delete: `python/helaicopter_api/router/dispatch.py`
- Delete: `python/helaicopter_api/router/workers.py`
- Delete: related application/schema/adapter/port modules
- Modify: `python/helaicopter_api/router/router.py`
- Modify: `python/helaicopter_api/server/lifespan.py`
- Modify: `python/helaicopter_api/server/openapi.py`
- Modify: `python/helaicopter_api/server/openapi_artifacts.py`
- Modify: `python/helaicopter_api/application/gateway.py`
- Modify: `python/helaicopter_api/server/config.py`
- Modify: `python/helaicopter_api/schema/__init__.py`
- Modify: `python/helaicopter_api/adapters/__init__.py`
- Modify: `python/helaicopter_api/ports/__init__.py`

- [ ] **Step 1: Write failing backend tests that prove removed routes are no longer registered**

Add or update a routing/openapi-style test to assert `/orchestration/oats`, `/dispatch/*`, and `/workers/*` are absent from the app router/openapi surface.

- [ ] **Step 2: Run the targeted backend test and confirm it fails**

Run: `uv run --group dev pytest tests/test_api_openapi.py -q`

- [ ] **Step 3: Remove router registration, startup wiring, schemas, services, adapters, and ports**

Make the backend boot without orchestration, dispatch, or worker lifecycle dependencies. Clean up imports and shared enums/types accordingly.

- [ ] **Step 4: Re-run the targeted backend test and confirm it passes**

Run: `uv run --group dev pytest tests/test_api_openapi.py -q`

- [ ] **Step 5: Commit**

```bash
git add python
git commit -m "refactor: remove orchestration backend control plane"
```

## Task 3: Remove the packaged OATS runtime and repo references

**Files:**
- Delete: `python/oats/*`
- Modify: `pyproject.toml`
- Modify: `package.json`
- Modify: `README.md`
- Delete or update: orchestration-only examples/docs/tests

- [ ] **Step 1: Write failing tests for packaging/docs assumptions that still mention OATS**

Add or update a small test around repo/runtime configuration or docs indexing so it fails while OATS references still exist.

- [ ] **Step 2: Run the targeted test and confirm it fails**

Run: `uv run --group dev pytest tests/test_backend_settings.py -q`

- [ ] **Step 3: Remove `python/oats`, package/script references, and documentation**

Delete the packaged runtime and all repo-level references that imply Helaicopter owns orchestration.

- [ ] **Step 4: Re-run the targeted test and confirm it passes**

Run: `uv run --group dev pytest tests/test_backend_settings.py -q`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml package.json README.md python tests
git commit -m "chore: remove packaged oats runtime and docs"
```

## Task 4: Full verification and cleanup

**Files:**
- Modify: any remaining imports/tests uncovered by verification

- [ ] **Step 1: Run frontend unit tests**

Run: `node --test src/lib/client/schemas/shared.test.ts src/lib/docs.test.ts`

- [ ] **Step 2: Run backend targeted tests**

Run: `uv run --group dev pytest -q tests/test_backend_settings.py tests/test_api_openapi.py tests/test_api_conversations.py`

- [ ] **Step 3: Run lint**

Run: `npm run lint`

- [ ] **Step 4: Run production build**

Run: `npm run build`

- [ ] **Step 5: Commit any final cleanup**

```bash
git add -A
git commit -m "test: verify orchestration removal"
```
