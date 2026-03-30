# FastMCP External Agent Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mount a curated FastMCP server on the existing FastAPI backend so external agents can read Helaicopter data and trigger conversation evaluations safely.

**Architecture:** Build a backend-owned FastMCP adapter from the existing FastAPI app, use explicit route maps to allow safe read routes plus evaluation creation, then mount the MCP ASGI app into the FastAPI application without breaking the current HTTP API.

**Tech Stack:** Python 3.13, FastAPI, FastMCP, Pydantic v2, pytest, httpx/TestClient.

---

### Task 1: Restore a verifiable backend baseline

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_api_smoke.py`

- [ ] **Step 1: Add the missing dependency coverage test target**

Confirm the current backend import path fails because `cryptography` is missing:

```bash
uv run --group dev pytest tests/test_api_smoke.py -q
```

Expected: import-time failure mentioning `ModuleNotFoundError: No module named 'cryptography'`.

- [ ] **Step 2: Add the missing runtime dependency**

Update `pyproject.toml` dependencies to include `cryptography` so the existing auth layer can import cleanly during test collection.

- [ ] **Step 3: Re-sync the Python environment**

Run:

```bash
uv sync --group dev
```

Expected: environment updates successfully and includes `cryptography`.

- [ ] **Step 4: Verify the baseline import path is restored**

Run:

```bash
uv run --group dev pytest tests/test_api_smoke.py -q
```

Expected: existing smoke tests collect and pass.

### Task 2: Add failing MCP integration tests

**Files:**
- Create: `tests/test_api_mcp.py`

- [ ] **Step 1: Write the failing test for MCP mount availability**

Add a test that creates the FastAPI app and asserts the mounted route tree includes an MCP path.

- [ ] **Step 2: Write the failing test for MCP transport health**

Add a test client request against the mounted MCP path or associated transport endpoints and assert the response is successful enough to prove the app is mounted.

- [ ] **Step 3: Write the failing test for route allowlisting**

Add tests that assert:

- safe routes such as analytics/conversations are present in the generated MCP surface
- excluded routes such as auth/workers/database refresh are absent

- [ ] **Step 4: Run the new test file and confirm failure**

Run:

```bash
uv run --group dev pytest tests/test_api_mcp.py -q
```

Expected: tests fail because no MCP integration exists yet.

### Task 3: Implement the FastMCP builder and mount it

**Files:**
- Create: `python/helaicopter_api/server/mcp.py`
- Modify: `python/helaicopter_api/server/main.py`

- [ ] **Step 1: Add FastMCP dependency**

Update `pyproject.toml` to include a current FastMCP version range compatible with the docs-driven integration.

- [ ] **Step 2: Build the MCP factory module**

Create `python/helaicopter_api/server/mcp.py` with:

- a FastMCP builder from the FastAPI app
- explicit route maps for safe GET resources/templates
- an allowlist for evaluation creation as a tool
- explicit exclusions for auth, workers, refresh, and other operational writes

- [ ] **Step 3: Mount the MCP ASGI app into the FastAPI factory**

Update `create_app()` so the returned FastAPI app mounts the MCP app at `/mcp` while preserving existing middleware and routers.

- [ ] **Step 4: Run the MCP tests**

Run:

```bash
uv run --group dev pytest tests/test_api_mcp.py -q
```

Expected: new MCP integration tests pass.

### Task 4: Verify regression safety on the backend contract

**Files:**
- Modify: `tests/test_api_smoke.py` if needed

- [ ] **Step 1: Run smoke coverage**

Run:

```bash
uv run --group dev pytest tests/test_api_smoke.py tests/test_api_mcp.py -q
```

Expected: all targeted app-factory and MCP smoke tests pass.

- [ ] **Step 2: Run a broader backend API slice**

Run:

```bash
uv run --group dev pytest tests/test_api_smoke.py tests/test_api_mcp.py tests/test_api_evaluations.py tests/test_api_conversations.py -q
```

Expected: the backend routes still behave correctly with MCP mounted.

### Task 5: Regenerate artifacts and prepare branch for review

**Files:**
- Modify: `public/openapi/helaicopter-api.json` if generated output changes
- Modify: `public/openapi/helaicopter-api.yaml` if generated output changes

- [ ] **Step 1: Regenerate OpenAPI artifacts if needed**

Run:

```bash
npm run api:openapi
```

Expected: artifacts regenerate cleanly. If no diff, leave them untouched.

- [ ] **Step 2: Run final verification**

Run:

```bash
uv run --group dev pytest tests/test_api_smoke.py tests/test_api_mcp.py tests/test_api_evaluations.py tests/test_api_conversations.py -q
```

Expected: passing targeted verification for the implemented feature.

- [ ] **Step 3: Review diff and commit**

Run:

```bash
git status --short
git diff --stat
git add pyproject.toml python/helaicopter_api/server/main.py python/helaicopter_api/server/mcp.py tests/test_api_mcp.py docs/superpowers/specs/2026-03-30-fastmcp-external-agent-surface-design.md docs/superpowers/plans/2026-03-30-fastmcp-external-agent-surface.md
git commit -m "feat: add fastmcp external agent surface"
```

- [ ] **Step 4: Push and create PR**

Run:

```bash
git push -u origin codex/fastmcp-agent-surface
gh pr create --title "feat: add FastMCP external agent surface" --body-file .git/PR_BODY_FASTMCP.md
```

Expected: a reviewable PR URL is created. If GitHub auth or remote permissions block this step, capture the exact failure and report it.
