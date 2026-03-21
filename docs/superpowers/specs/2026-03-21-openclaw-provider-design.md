# OpenClaw Provider Design

## Goal

Add OpenClaw as a first-class conversation provider across the entire product so OpenClaw sessions appear alongside Claude and Codex in conversation lists, detail views, filters, analytics, and backend export/indexing paths.

## Context

This repo already supports two local-first providers:

- Claude Code, sourced from `~/.claude/projects/*/*.jsonl`
- Codex, sourced from `~/.codex/sessions/YYYY/MM/DD/*.jsonl` with SQLite enrichment

OpenClaw introduces a third shape:

- Session metadata store files at `~/.openclaw/agents/<agentId>/sessions/sessions.json`
- Transcript files at `~/.openclaw/agents/<agentId>/sessions/<sessionId>.jsonl`
- Transcript JSONL lines that are event-oriented rather than conversation-only

The local sample confirms the transcript shape is materially different from both Claude and Codex:

- Header events such as `session`, `model_change`, `thinking_level_change`, `custom`
- `message` events whose nested `message.role` can be `user`, `assistant`, or `toolResult`
- Assistant content blocks including `text`, `thinking`, and `toolCall`
- Separate tool result transcript entries keyed by `toolCallId`
- Assistant messages with embedded `provider`, `model`, `usage`, and `cost`

That means OpenClaw should not be aliased to Codex. It needs its own provider identity and its own normalization adapter.

## Requirements

### Functional

- Discover OpenClaw conversations from all `~/.openclaw/agents/*/sessions/` directories
- Normalize OpenClaw transcripts into the app's existing conversation contracts
- Label OpenClaw sessions as `openclaw` everywhere in the product
- Include OpenClaw in all provider filters and provider-aware aggregations
- Show OpenClaw conversations in conversation list/detail views and analytics
- Use OpenClaw agent identity as the canonical project/grouping key
- Preserve transcript `cwd` as secondary metadata, not as the primary project key
- Use transcript-embedded usage and cost when available

### Non-Functional

- Preserve the existing frontend/backend contract style where possible
- Avoid a large generic-provider refactor unless required by the OpenClaw shape
- Keep parsing streaming-friendly and capable of handling large JSONL transcripts
- Degrade safely when some OpenClaw transcripts do not contain complete usage/cost data

## Non-Goals

- Re-architect the entire provider system into a generic plugin framework in this change
- Fabricate DAG/subagent structures when the transcript does not justify them
- Reclassify OpenClaw sessions as Codex sessions based on underlying model/provider strings

## Recommended Approach

Add an OpenClaw-specific backend adapter behind the existing normalized conversation interfaces, then extend provider enums, filters, analytics, and frontend labels to include `openclaw`.

This preserves the current architecture:

- provider-specific discovery and parsing at the ingestion layer
- provider-agnostic normalized contracts above that layer
- minimal churn in the frontend, which already expects unified conversation payloads

## Alternatives Considered

### 1. Generic Provider Refactor First

Refactor Claude and Codex ingestion into a new pluggable provider abstraction before adding OpenClaw.

Pros:

- cleaner long-term abstraction if more providers are expected soon

Cons:

- much larger blast radius
- delays user value
- increases the chance of regressions in existing providers

Rejected because the current repo already has a workable provider-aware shape, and OpenClaw can fit behind it.

### 2. Treat OpenClaw As Codex-Compatible

Map OpenClaw to `codex` because many transcripts may use OpenAI Codex-backed models.

Pros:

- minimal code initially

Cons:

- wrong provenance in UI and analytics
- broken expectations for project grouping
- impossible to distinguish native Codex CLI sessions from OpenClaw sessions

Rejected because provider identity in this app is about source system, not just model vendor.

## Design

### Provider Identity

Introduce `openclaw` as a first-class provider everywhere the repo currently models `claude` and `codex`.

Provider identity rules:

- `claude` means Claude Code local artifacts
- `codex` means Codex local artifacts
- `openclaw` means OpenClaw local artifacts

Underlying OpenClaw transcript fields like `provider: "openai-codex"` remain model metadata, not top-level provider identity.

### Discovery

Discovery should scan:

- `~/.openclaw/agents/*/sessions/sessions.json`
- adjacent `*.jsonl` transcript files in the same sessions directory

Discovery scope is all agent directories, not just `main`.

Each discovered conversation should capture:

- `agent_id` from the directory name
- `session_id` from the transcript/store entry
- `transcript_path`
- `store_path`
- optional session-store metadata from `sessions.json`

### Project And Conversation Identity

OpenClaw grouping should be agent-centric, not cwd-centric.

Canonical identity proposal:

- conversation id: `openclaw:<agentId>:<sessionId>`
- project path: `openclaw:agent:<agentId>`

Secondary metadata:

- transcript header `cwd`
- transcript/session model provider
- transcript/session model id

This keeps grouping stable even when multiple OpenClaw agents share a workspace or when `cwd` is absent, generic, or misleading.

Compatibility rule:

- the synthetic OpenClaw project path is an app-level provider key, not a real filesystem path
- any path-derived UI or API logic that currently assumes provider project keys always represent real workspace paths must treat `openclaw:*` as provider-owned identifiers instead

### Transcript Parsing

OpenClaw transcripts should be parsed as event streams.

The parser should:

1. Read the `session` header line
2. Track latest model/provider information from `model_change` and assistant messages
3. Materialize only transcript `message` events into normalized message objects
4. Convert assistant content blocks into existing display blocks:
   - `text` -> text block
   - `thinking` -> thinking block
   - `toolCall` -> tool-call block
5. Convert separate `toolResult` messages into tool result blocks paired by `toolCallId`
6. Aggregate usage/cost from assistant messages

Important behavioral detail:

- OpenClaw transcript ordering is already meaningful through line order and parent chaining
- The app should preserve transcript order rather than attempting to rebuild a separate chronological model from parent pointers alone

Tool-result edge cases:

- unmatched `toolResult` entries should still be preserved in raw/normalized message output, but rendered as unpaired tool-result content rather than discarded
- repeated `toolResult` entries for the same `toolCallId` should preserve transcript order and be shown as repeated outputs, not collapsed unless current app contracts already require that behavior

### Summary Extraction

Conversation summaries should derive:

- first message from the first real user text block
- message count from normalized user/assistant messages
- tool use count from assistant `toolCall` blocks
- tool failure count from `toolResult.isError`
- model from the latest known assistant/model-change value
- timestamps from transcript line timestamps
- total usage and total cost from aggregated assistant usage snapshots

Usage aggregation rule:

- treat assistant `usage` objects as cumulative conversation snapshots, not per-message deltas
- use the latest assistant message carrying a valid `usage` object as the authoritative conversation total
- if multiple assistant messages contain usage, do not sum them

Cost aggregation rule:

- if the latest authoritative usage snapshot contains `usage.cost`, use that transcript-embedded cost as the authoritative total
- if transcript cost is missing on the authoritative usage snapshot but raw usage totals are present, downstream semantics code may estimate cost from usage and model metadata
- if neither authoritative cost nor enough usage data exists, normalized cost fields should remain `null`/missing rather than being forced to `0`

Fallback behavior:

- if transcript cost is missing but usage is present, later semantics code may estimate cost
- if both are missing, analytics should still include the conversation with unknown-cost semantics rather than dropping it
- unknown cost should remain nullable through API/normalization layers so the UI and analytics can distinguish "missing" from actual zero

### Session Store Usage

`sessions.json` should be treated as metadata enrichment, not as the source of truth for transcript content.

Use it for:

- session routing/display labels when available
- last activity metadata
- optional agent/session enrichment

Do not depend on it to reconstruct message history.

### API And Contract Changes

Backend and frontend schemas should be extended to accept `openclaw` wherever provider names are modeled.

Expected changes:

- API response enums/unions
- conversation summaries
- conversation detail payloads
- analytics provider filters
- subscription or pricing/provider settings where provider names are validated

The normalized contract itself should stay stable unless OpenClaw exposes a truly new concept that cannot be represented today.

### Analytics

Analytics should treat OpenClaw as a third provider bucket.

Rules:

- provider filter adds `openclaw`
- provider-specific counts, costs, tool breakdowns, model breakdowns, and daily usage include OpenClaw
- transcript cost and usage should be authoritative when present
- model/vendor semantics can still be used for fallback estimation, but they must not overwrite explicit transcript cost
- conversations with missing cost still count toward conversation, tool, and model analytics; only cost-specific aggregates should omit or null-handle the missing value rather than coercing it to zero

This implies analytics logic must distinguish:

- source provider: `openclaw`
- model vendor/provider metadata inside the conversation

### UI

Frontend behavior should become:

- Provider filter: `All`, `Claude`, `Codex`, `OpenClaw`
- Conversation cards show OpenClaw badge/label based on source provider
- Detail views render normalized messages without special-casing OpenClaw in the UI
- Raw view remains available for exact transcript inspection

Project labeling for OpenClaw should default to the agent identity rather than cwd-derived workspace names.

### Export And Indexing

OpenClaw should participate in backend export/indexing through the same normalized conversation contracts used by Claude and Codex.

Requirements:

- export/indexing pipelines must ingest OpenClaw conversations once they are normalized
- exported/indexed records must preserve source provenance as `provider = "openclaw"`
- exported/indexed records should also preserve OpenClaw-specific source metadata where the existing schema allows it, especially:
  - `agent_id`
  - transcript path
  - transcript/store-discovered project path derived from agent identity

Non-requirement:

- this change does not introduce a separate OpenClaw-only export schema

If a current export/index schema lacks fields for OpenClaw-only metadata, normalized inclusion with correct provider provenance is sufficient for the first pass.

### DAGs And Subagents

OpenClaw transcripts appear to use parent-chained event logs, but that does not automatically imply the same conversation DAG semantics currently used for Claude/Codex.

Recommendation:

- support OpenClaw in conversation list, detail, raw, and analytics in the first pass
- only expose DAG/subagent structures for OpenClaw where real structure is derivable from actual stored relationships
- do not fabricate DAG nodes from event parent pointers alone

This avoids misleading visualizations.

Scope rule:

- DAG/subagent support for OpenClaw is out of scope for the initial implementation unless currently stored OpenClaw relationships prove sufficient without speculative inference

## Affected Areas

Likely code areas:

- backend config for OpenClaw root path discovery
- backend provider/discovery ports and adapters
- OpenClaw transcript parser/normalizer
- API routers/application services for conversations and analytics
- frontend schemas/normalizers/hooks
- provider labels, badges, and filter UI
- tests for API, normalization, analytics, and export pipeline
- README and data source documentation

## Testing Strategy

### Backend

- fixture-based tests with real OpenClaw transcript snippets
- summary extraction tests
- detail parsing tests including tool call/result pairing
- provider filter tests for `openclaw`
- analytics aggregation tests for mixed Claude/Codex/OpenClaw datasets
- discovery tests across multiple `agents/*/sessions/` directories

### Frontend

- schema/normalization coverage for `openclaw`
- provider filter UI tests
- conversation route/detail rendering tests using OpenClaw payloads

### Regression

- existing Claude/Codex tests must remain green
- no provider defaulting logic should accidentally coerce OpenClaw into Codex

## Risks

### Transcript Variability

OpenClaw transcript versions may vary across installs. The parser should ignore unknown event types and normalize only the parts it understands.

### Cost Semantics

OpenClaw transcript cost fields may reflect runtime-computed values that differ from this app's current fallback pricing logic. Explicit transcript cost should win when present to avoid double-estimation drift.

### Store/Transcript Mismatch

`sessions.json` and transcript contents may disagree. Transcript content should remain authoritative for message history; store metadata should be best-effort enrichment.

### DAG Ambiguity

The event `parentId` chain is not proof of conversation tree semantics. Avoid overfitting DAG logic in the first implementation.

## Rollout Recommendation

Deliver OpenClaw as a single user-visible feature, but implement it internally in this order:

1. backend discovery and transcript parsing
2. normalized API contract extension for `openclaw`
3. analytics/provider filter updates
4. frontend provider labels and detail/list integration
5. DAG support only if real structure is available

## Success Criteria

- OpenClaw transcripts from all local agent directories are discoverable
- OpenClaw sessions appear in the conversations list with provider label `OpenClaw`
- OpenClaw sessions open in conversation detail and raw views
- analytics and provider filters include OpenClaw without breaking Claude/Codex
- project grouping is based on OpenClaw agent identity, not cwd
- transcript-embedded usage/cost is preserved in summaries and analytics when present
