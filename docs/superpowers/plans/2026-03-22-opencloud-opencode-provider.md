# OpenCloud / OpenCode Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenCloud as a first-class provider that reads real OpenCode session data and surfaces conversations, tool calls, and token usage throughout the app.

**Architecture:** Extend the existing provider-aware backend with a readonly OpenCode SQLite adapter and normalize its session/message/part data into the current conversation contracts. Then widen provider vocab, analytics/export logic, and frontend labels/filters so OpenCloud behaves like the other first-class providers.

**Tech Stack:** Python, FastAPI, SQLite, Next.js, TypeScript, Playwright

---

### Task 1: Add OpenCloud backend storage and conversation parsing

**Files:**
- Create: `python/helaicopter_api/ports/opencloud_sqlite.py`
- Create: `python/helaicopter_api/adapters/opencloud_sqlite/__init__.py`
- Create: `python/helaicopter_api/adapters/opencloud_sqlite/store.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `python/helaicopter_api/server/config.py`
- Modify: `python/helaicopter_api/application/conversations.py`
- Test: `tests/test_backend_settings.py`
- Test: `tests/test_api_conversations.py`

- [ ] Step 1: Write failing backend settings and conversation tests for OpenCloud discovery and detail shaping.
- [ ] Step 2: Run the focused pytest cases and verify they fail for missing OpenCloud support.
- [ ] Step 3: Implement readonly OpenCode SQLite access and service wiring.
- [ ] Step 4: Implement OpenCloud summary/detail normalization in the conversations application.
- [ ] Step 5: Re-run the focused pytest cases and verify they pass.

### Task 2: Extend provider vocab, semantics, analytics, and export paths

**Files:**
- Modify: `python/helaicopter_domain/vocab.py`
- Modify: `python/helaicopter_semantics/models.py`
- Modify: `python/helaicopter_api/schema/analytics.py`
- Modify: `python/helaicopter_api/pure/analytics.py`
- Modify: `python/helaicopter_db/export_pipeline.py`
- Modify: `python/helaicopter_db/utils.py`
- Test: `tests/test_semantics.py`
- Test: `tests/test_analytics_core.py`
- Test: `tests/test_export_pipeline.py`

- [ ] Step 1: Add failing tests for OpenCloud provider resolution, analytics buckets, and export inclusion.
- [ ] Step 2: Run those tests and confirm the failures are specific to missing OpenCloud support.
- [ ] Step 3: Widen provider vocab and semantics for OpenCloud.
- [ ] Step 4: Add OpenCloud analytics and export handling.
- [ ] Step 5: Re-run the targeted tests and verify they pass.

### Task 3: Extend frontend contracts and provider UI

**Files:**
- Modify: `src/lib/types.ts`
- Modify: `src/lib/routes.ts`
- Modify: `src/lib/client/schemas/shared.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/components/ui/provider-filter.tsx`
- Modify: `src/components/conversation/conversation-list.tsx`
- Modify: `src/components/conversation/conversation-viewer.tsx`
- Modify: `src/components/analytics/cost-breakdown-card.tsx`
- Modify: `src/views/plans/plans-index-view.tsx`
- Modify: `src/features/plans/components/plan-panel.tsx`
- Modify: `src/app/page.tsx`
- Test: `src/lib/client/normalize.test.ts`
- Test: `src/app/conversations/[...segments]/page.test.ts`

- [ ] Step 1: Add failing frontend tests for OpenCloud provider parsing, normalization, and labels.
- [ ] Step 2: Run the frontend tests and verify they fail because `opencloud` is unknown.
- [ ] Step 3: Implement the minimal frontend type/schema/UI changes.
- [ ] Step 4: Re-run the targeted frontend tests and verify they pass.

### Task 4: Validate end-to-end and write report

**Files:**
- Create: `examples/opencloud_opencode_orchestration_run.md`
- Create: `/tmp/helaicopter_opencloud_integration_report.md`

- [ ] Step 1: Materialize an orchestration run spec for the work using the requested orchestrate-run framework.
- [ ] Step 2: Run targeted and broader validation commands for backend and frontend.
- [ ] Step 3: Start the app locally and verify the OpenCloud provider in the UI with Playwright.
- [ ] Step 4: Write the final detailed report with architecture, files changed, tests run, verification results, and gaps.
