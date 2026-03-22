# OpenClaw Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenClaw as a first-class provider across conversation ingestion, normalized API responses, analytics, export/indexing, and frontend provider surfaces.

**Architecture:** Extend the existing provider-aware backend with a dedicated OpenClaw discovery/parser adapter that normalizes OpenClaw transcripts into the current conversation contracts used by Claude and Codex. Then widen provider vocab/types, thread the new provider through analytics/export paths, and finally update the frontend filters and labels so OpenClaw appears everywhere without inventing provider-specific UI behavior.

**Tech Stack:** FastAPI, Pydantic, Python 3.13, pytest, SQLAlchemy-backed app store adapters, Next.js App Router, React, TypeScript, Zod, SWR.

---

## File Map

- `python/helaicopter_domain/vocab.py`
  Extend canonical provider literals to include `openclaw`.
- `python/helaicopter_api/server/config.py`
  Add OpenClaw filesystem root settings and derived session-store properties.
- `python/helaicopter_api/bootstrap/services.py`
  Wire a concrete OpenClaw store/reader into the backend service graph.
- `python/helaicopter_api/ports/openclaw_fs.py`
  Create a focused port for OpenClaw session-store discovery and transcript access.
- `python/helaicopter_api/adapters/openclaw_fs/store.py`
  Implement local filesystem discovery for `~/.openclaw/agents/*/sessions/`.
- `python/helaicopter_api/application/openclaw_payloads.py`
  Parse OpenClaw JSONL transcript lines and normalize event/message shapes.
- `python/helaicopter_api/application/conversations.py`
  Merge OpenClaw live summaries/details into the current conversation read path.
- `python/helaicopter_api/schema/conversations.py`
  Update response docs/comments where they currently imply only Claude/Codex.
- `python/helaicopter_semantics/models.py`
  Teach provider resolution about `openclaw`.
- `python/helaicopter_api/pure/analytics.py`
  Add OpenClaw provider buckets, counters, and cost handling.
- `python/helaicopter_api/schema/analytics.py`
  Widen provider filters and response typing for OpenClaw analytics.
- `python/helaicopter_db/export_pipeline.py`
  Include OpenClaw in historical export iteration and preserve provider provenance.
- `tests/test_api_conversations.py`
  Add end-to-end OpenClaw live-source fixtures and assertions.
- `tests/test_semantics.py`
  Lock canonical provider resolution for OpenClaw.
- `tests/test_analytics_core.py`
  Add OpenClaw analytics/provider-filter coverage.
- `tests/test_export_pipeline.py`
  Add OpenClaw export inclusion/dedup/provenance tests.
- `tests/test_backend_settings.py`
  Add OpenClaw config path coverage.
- `src/lib/client/schemas/shared.ts`
  Extend provider enums and filter enums to include `openclaw`.
- `src/lib/types.ts`
  Widen frontend provider unions and analytics structures.
- `src/lib/client/normalize.ts`
  Preserve `openclaw` instead of coercing non-Codex providers to Claude.
- `src/lib/client/normalize.test.ts`
  Add provider normalization coverage for OpenClaw.
- `src/components/ui/provider-filter.tsx`
  Add the OpenClaw option to the shared provider selector.
- `src/components/conversation/conversation-list.tsx`
  Make provider filtering and token-cost display aware of OpenClaw.
- `src/components/conversation/conversation-viewer.tsx`
  Add OpenClaw provider labeling/styling in detail views.
- `src/features/plans/components/plan-panel.tsx`
  Widen provider label helpers so OpenClaw-linked plans render safely.
- `src/views/plans/plans-index-view.tsx`
  Widen provider label helpers so OpenClaw-linked plan rows render safely.
- `src/components/analytics/cost-breakdown-card.tsx`
  Ensure provider breakdown selection handles OpenClaw.
- `src/app/page.tsx`
  Extend homepage provider-filter affordances and any hard-coded provider cards.
- `README.md`
  Document OpenClaw as a third local data source.

## Task 1: Add backend OpenClaw discovery and transcript parsing

**Files:**
- Create: `python/helaicopter_api/ports/openclaw_fs.py`
- Create: `python/helaicopter_api/adapters/openclaw_fs/store.py`
- Create: `python/helaicopter_api/application/openclaw_payloads.py`
- Modify: `python/helaicopter_api/server/config.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `tests/test_backend_settings.py`
- Test: `tests/test_api_conversations.py`

- [ ] **Step 1: Write the failing backend fixture tests**

  In `tests/test_api_conversations.py`, add a minimal OpenClaw fixture tree under a temp `~/.openclaw` equivalent:
  - `agents/main/sessions/sessions.json`
  - `agents/main/sessions/<session-id>.jsonl`
  - `agents/secondary/sessions/...`

  Cover:
  - OpenClaw sessions are discovered from all agent directories
  - the canonical `project_path` is agent-based, not cwd-based
  - assistant `toolCall` + separate `toolResult` entries shape into the existing message blocks
  - unmatched `toolResult` messages are preserved rather than dropped
  - unknown OpenClaw event types are ignored safely without aborting transcript parsing

- [ ] **Step 2: Run the targeted test to verify RED**

  Run:
  ```bash
  uv run --group dev pytest -q tests/test_api_conversations.py -k openclaw
  ```
  Expected: FAIL because no OpenClaw config/store/parser exists yet.

- [ ] **Step 3: Add OpenClaw settings and service wiring**

  In `python/helaicopter_api/server/config.py`, add:
  ```py
  openclaw_dir: Path = Field(
      default_factory=lambda: Path.home() / ".openclaw",
      description="Root of the OpenClaw data directory (typically ~/.openclaw).",
  )
  ```
  Add matching `CliSettings` properties for the OpenClaw root and agent sessions path helpers.

  In `python/helaicopter_api/bootstrap/services.py`, add a new `openclaw_store` service field and construct it from the new adapter.

- [ ] **Step 4: Implement the OpenClaw filesystem adapter**

  Create `python/helaicopter_api/ports/openclaw_fs.py` with narrow models/protocols:
  ```py
  class OpenClawTranscriptArtifact(BaseModel):
      agent_id: str
      session_id: str
      path: str
      modified_at: float
      content: str
  ```
  and a protocol that exposes:
  - `list_session_artifacts()`
  - `read_session_artifact(agent_id, session_id)`
  - `read_session_store(agent_id)`

  Implement it in `python/helaicopter_api/adapters/openclaw_fs/store.py` by walking `agents/*/sessions/`.

- [ ] **Step 5: Implement OpenClaw transcript parsing**

  In `python/helaicopter_api/application/openclaw_payloads.py`, parse JSONL line-by-line and expose helpers that:
  - recognize `session`, `model_change`, `thinking_level_change`, `custom`, and `message`
  - extract the latest model/provider snapshot
  - convert assistant `content` blocks into text/thinking/tool-call units
  - preserve separate `toolResult` messages with `toolCallId`, `toolName`, `isError`
  - treat assistant usage as cumulative snapshots and select the latest valid snapshot instead of summing

- [ ] **Step 6: Thread OpenClaw into live conversations**

  In `python/helaicopter_api/application/conversations.py`, add OpenClaw-specific list/detail helpers parallel to the Claude/Codex live paths:
  - include them in `list_conversations(...)`
  - route OpenClaw project paths to OpenClaw detail resolution in `get_conversation(...)`
  - generate `provider="openclaw"`, `project_path="openclaw:agent:<agentId>"`, and stable `conversation_ref`

- [ ] **Step 7: Run the backend conversation tests to verify GREEN**

  Run:
  ```bash
  uv run --group dev pytest -q tests/test_backend_settings.py tests/test_api_conversations.py
  ```
  Expected: PASS, including the new OpenClaw fixture coverage.

- [ ] **Step 8: Commit**

  Run:
  ```bash
  git add python/helaicopter_api/ports/openclaw_fs.py python/helaicopter_api/adapters/openclaw_fs/store.py python/helaicopter_api/application/openclaw_payloads.py python/helaicopter_api/server/config.py python/helaicopter_api/bootstrap/services.py python/helaicopter_api/application/conversations.py tests/test_backend_settings.py tests/test_api_conversations.py
  git commit -m "feat: add OpenClaw live conversation reader"
  ```

## Task 2: Extend provider vocab and semantics for OpenClaw

**Files:**
- Modify: `python/helaicopter_domain/vocab.py`
- Modify: `python/helaicopter_semantics/models.py`
- Modify: `python/helaicopter_api/schema/conversations.py`
- Modify: `python/helaicopter_api/schema/analytics.py`
- Modify: `tests/test_semantics.py`

- [ ] **Step 1: Write the failing provider-resolution tests**

  In `tests/test_semantics.py`, add cases that prove:
  - explicit `provider="openclaw"` resolves to OpenClaw
  - `project_path` prefixed with `openclaw:` resolves to OpenClaw
  - OpenClaw is not coerced to Codex even when transcript model/provider strings look OpenAI-ish

- [ ] **Step 2: Run the semantics test to verify RED**

  Run:
  ```bash
  uv run --group dev pytest -q tests/test_semantics.py -k openclaw
  ```
  Expected: FAIL because provider literals and heuristics do not include OpenClaw yet.

- [ ] **Step 3: Expand canonical provider literals**

  Update `python/helaicopter_domain/vocab.py`:
  ```py
  ProviderName = Literal["claude", "codex", "openclaw"]
  ProviderSelection = Literal["all", "claude", "codex", "openclaw"]
  ```

- [ ] **Step 4: Teach semantics provider resolution about OpenClaw**

  In `python/helaicopter_semantics/models.py`, update `ProviderIdentifier` and `resolve_provider(...)` priority so:
  - explicit provider `openclaw` wins
  - `project_path.startswith("openclaw:")` is authoritative
  - model heuristics do not remap OpenClaw back to Codex when OpenClaw provenance is already known

- [ ] **Step 5: Widen API provider docs/enums**

  Update provider-derived schema aliases in:
  - `python/helaicopter_api/schema/conversations.py`
  - `python/helaicopter_api/schema/analytics.py`

  Keep response contracts stable; only widen provider values and descriptions.

- [ ] **Step 6: Run the targeted provider tests to verify GREEN**

  Run:
  ```bash
  uv run --group dev pytest -q tests/test_semantics.py
  ```
  Expected: PASS with the new OpenClaw cases.

- [ ] **Step 7: Commit**

  Run:
  ```bash
  git add python/helaicopter_domain/vocab.py python/helaicopter_semantics/models.py python/helaicopter_api/schema/conversations.py python/helaicopter_api/schema/analytics.py tests/test_semantics.py
  git commit -m "feat: add OpenClaw provider vocab"
  ```

## Task 3: Include OpenClaw in analytics and export/indexing

**Files:**
- Modify: `python/helaicopter_api/pure/analytics.py`
- Modify: `python/helaicopter_db/export_pipeline.py`
- Modify: `tests/test_analytics_core.py`
- Modify: `tests/test_export_pipeline.py`

- [ ] **Step 1: Write the failing analytics and export tests**

  Add tests that prove:
  - provider-filtered analytics can return only OpenClaw conversations
  - mixed-provider analytics preserve separate OpenClaw counts/costs/tool breakdowns
  - OpenClaw rows flow through `iter_export_rows(...)`
  - exported envelopes preserve `provider="openclaw"` provenance rather than collapsing to Claude/Codex
  - existing Claude/Codex analytics provider filters still behave the same after widening provider unions

- [ ] **Step 2: Run the targeted tests to verify RED**

  Run:
  ```bash
  uv run --group dev pytest -q tests/test_analytics_core.py tests/test_export_pipeline.py -k openclaw
  ```
  Expected: FAIL because analytics buckets and export iterators are still Claude/Codex-only.

- [ ] **Step 3: Extend analytics provider structures**

  In `python/helaicopter_api/pure/analytics.py`:
  - update `AnalyticsProvider`
  - add OpenClaw fields to provider-specific dataclasses where the current structure is explicitly Claude/Codex-shaped
  - ensure missing OpenClaw cost stays nullable/omitted in cost math instead of being coerced to zero

  If the current dataclass shape is too rigid, refactor provider-specific counters to keyed maps in the smallest possible way that keeps existing API payloads stable or intentionally updated in one place.

- [ ] **Step 4: Extend export iteration**

  In `python/helaicopter_db/export_pipeline.py`, add `_iter_openclaw_historical_envelopes(settings)` parallel to the Claude and Codex iterators. Reuse the new OpenClaw normalization helpers instead of inventing a second parser path. Ensure `summary.projectPath` remains agent-based and `conversation_id(...)` sees the source provider as OpenClaw.

- [ ] **Step 5: Run the targeted tests to verify GREEN**

  Run:
  ```bash
  uv run --group dev pytest -q tests/test_analytics_core.py tests/test_export_pipeline.py
  ```
  Expected: PASS, including the new OpenClaw analytics/export assertions.

- [ ] **Step 6: Commit**

  Run:
  ```bash
  git add python/helaicopter_api/pure/analytics.py python/helaicopter_db/export_pipeline.py tests/test_analytics_core.py tests/test_export_pipeline.py
  git commit -m "feat: include OpenClaw in analytics and exports"
  ```

## Task 4: Widen frontend schemas, types, and provider normalization

**Files:**
- Modify: `src/lib/client/schemas/shared.ts`
- Modify: `src/lib/types.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/normalize.test.ts`

- [ ] **Step 1: Write the failing frontend normalization tests**

  In `src/lib/client/normalize.test.ts`, add OpenClaw cases that prove:
  - provider schemas accept `openclaw`
  - conversation summaries/details preserve `provider: "openclaw"`
  - non-Codex providers are not silently coerced to Claude

- [ ] **Step 2: Run the targeted frontend test to verify RED**

  Run:
  ```bash
  npm test -- src/lib/client/normalize.test.ts
  ```
  Expected: FAIL because frontend provider enums and normalization only recognize Claude/Codex.

- [ ] **Step 3: Widen shared provider enums and unions**

  Update:
  - `src/lib/client/schemas/shared.ts`
  - `src/lib/types.ts`

  Replace hard-coded `"claude" | "codex"` and provider arrays with OpenClaw-aware variants everywhere they model conversation providers, analytics providers, or subscription/evaluation providers that must remain compatible.

- [ ] **Step 4: Fix provider-preserving normalization**

  In `src/lib/client/normalize.ts`, remove branches like:
  ```ts
  stringOr(item.provider) === "codex" ? "codex" : "claude"
  ```
  Replace them with explicit preservation logic that accepts `openclaw` and fails safe for unknown values through existing schema validation.

- [ ] **Step 5: Run the targeted frontend tests to verify GREEN**

  Run:
  ```bash
  npm test -- src/lib/client/normalize.test.ts
  ```
  Expected: PASS with the new OpenClaw normalization cases.

- [ ] **Step 6: Commit**

  Run:
  ```bash
  git add src/lib/client/schemas/shared.ts src/lib/types.ts src/lib/client/normalize.ts src/lib/client/normalize.test.ts
  git commit -m "feat: add OpenClaw frontend provider types"
  ```

## Task 5: Add OpenClaw to frontend filters, labels, and docs

**Files:**
- Modify: `src/components/ui/provider-filter.tsx`
- Modify: `src/components/conversation/conversation-list.tsx`
- Modify: `src/components/conversation/conversation-viewer.tsx`
- Modify: `src/features/plans/components/plan-panel.tsx`
- Modify: `src/views/plans/plans-index-view.tsx`
- Modify: `src/components/analytics/cost-breakdown-card.tsx`
- Modify: `src/app/page.tsx`
- Modify: `README.md`
- Test: `src/app/conversations/[...segments]/page.test.ts`

- [ ] **Step 1: Write the failing UI tests**

  Add or update targeted tests that prove:
  - provider filters render an OpenClaw option
  - OpenClaw conversation payloads render without being mislabeled as Claude/Codex
  - project grouping/filter logic does not assume only `codex:` is a non-Claude namespace
  - OpenClaw conversations still open in the raw conversation view without provider-specific breakage

- [ ] **Step 2: Run the targeted test to verify RED**

  Run:
  ```bash
  npm test -- src/app/conversations/[...segments]/page.test.ts
  ```
  Expected: FAIL or remain incomplete because provider-filter UI and helper labeling are still two-provider assumptions.

- [ ] **Step 3: Update shared provider UI components**

  In `src/components/ui/provider-filter.tsx`, add `OpenClaw`.

  In the conversation/plans components, replace two-provider label helpers with explicit OpenClaw-aware mappings:
  ```ts
  const providerLabel = {
    claude: "Claude",
    codex: "Codex",
    openclaw: "OpenClaw",
  }[provider];
  ```

- [ ] **Step 4: Fix provider filtering logic**

  In `src/components/conversation/conversation-list.tsx`, stop using `projectPath.startsWith("codex:")` as a proxy for “not Claude”. Filter by explicit provider from the normalized API payload instead.

- [ ] **Step 5: Update docs**

  In `README.md`, document:
  - `~/.openclaw/agents/*/sessions/sessions.json`
  - `~/.openclaw/agents/*/sessions/*.jsonl`
  - OpenClaw as a third provider in the analytics/conversations UI

- [ ] **Step 6: Run the focused UI verification**

  Run:
  ```bash
  npm test -- src/app/conversations/[...segments]/page.test.ts
  npm test -- src/lib/client/normalize.test.ts
  ```
  Expected: PASS, with provider labels and filters accepting OpenClaw.

- [ ] **Step 7: Run the full cross-stack smoke verification**

  Run:
  ```bash
  uv run --group dev pytest -q tests/test_backend_settings.py tests/test_semantics.py tests/test_api_conversations.py tests/test_analytics_core.py tests/test_export_pipeline.py
  npm test -- src/lib/client/normalize.test.ts src/app/conversations/[...segments]/page.test.ts
  ```
  Expected: PASS across backend parsing, provider semantics, analytics/export, and frontend normalization.

- [ ] **Step 8: Commit**

  Run:
  ```bash
  git add src/components/ui/provider-filter.tsx src/components/conversation/conversation-list.tsx src/components/conversation/conversation-viewer.tsx src/features/plans/components/plan-panel.tsx src/views/plans/plans-index-view.tsx src/components/analytics/cost-breakdown-card.tsx src/app/page.tsx README.md src/app/conversations/[...segments]/page.test.ts
  git commit -m "feat: surface OpenClaw across UI filters and labels"
  ```
