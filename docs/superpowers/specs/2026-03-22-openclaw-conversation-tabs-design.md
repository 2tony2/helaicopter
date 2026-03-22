# OpenClaw Conversation Tabs Design

## Goal

Process and surface the maximum amount of OpenClaw conversation data available on the local machine, starting with a dedicated `OpenClaw` conversation tab and then promoting reusable concepts into existing shared tabs where they map cleanly.

## Context

Helaicopter already treats OpenClaw as a first-class provider, but the current implementation is intentionally thin:

- discovery reads only `~/.openclaw/agents/*/sessions/*.jsonl`
- summaries and detail views are transcript-driven
- only a subset of event types are parsed
- `sessions.json` state is not ingested
- archived transcript variants are ignored
- `~/.openclaw/memory/main.sqlite` is ignored
- provider-specific metadata has no dedicated contract or UI

The local OpenClaw installation contains materially richer artifacts:

- live transcripts at `~/.openclaw/agents/<agentId>/sessions/<sessionId>.jsonl`
- archived transcripts such as `*.jsonl.reset.<timestamp>` and `*.jsonl.deleted.<timestamp>`
- mutable session-store metadata at `~/.openclaw/agents/<agentId>/sessions/sessions.json`
- memory/index storage at `~/.openclaw/memory/main.sqlite`
- auxiliary provenance in config/log files under `~/.openclaw`

The local `sessions.json` entries already include high-value metadata that is not currently surfaced:

- routing and origin metadata
- token counters and context estimates
- model and auth overrides
- compaction bookkeeping
- `skillsSnapshot`
- `systemPromptReport`

This makes the current conversation tabs feel bare-bones for OpenClaw sessions even when the underlying machine has the data.

## Requirements

### Functional

- Discover OpenClaw data from all relevant local artifacts, not only live transcripts
- Preserve the current shared conversation summaries and message rendering behavior
- Add a provider-specific OpenClaw detail payload for metadata that does not belong in the shared contract
- Add an `OpenClaw` tab to the conversation viewer
- Ingest and expose archived transcript variants when available
- Expose `sessions.json` session-store metadata
- Expose `skillsSnapshot` and `systemPromptReport`
- Expose transcript diagnostics for non-message event types
- Expose `memory/main.sqlite` as supplemental provenance and storage diagnostics
- Reuse existing tabs only where concepts map cleanly to current abstractions

### Non-Functional

- Keep the shared transport contract stable for Claude, Codex, and OpenCloud
- Make OpenClaw-specific extensions typed rather than opaque blobs
- Preserve unknown or currently-unused OpenClaw event data instead of silently dropping it
- Avoid forcing an app-SQLite persistence refactor in the first pass
- Keep the first pass composable so the richer OpenClaw shape can later be persisted if needed

## Non-Goals

- Rebuild the entire conversation system around provider plugins
- Force all OpenClaw metadata into existing shared fields
- Invent OpenClaw subagent structures when the artifacts do not justify them
- Treat `memory/main.sqlite` as canonical conversation history

## Recommended Approach

Extend the existing live OpenClaw provider path into a richer stitched session-family reader, then expose the result through:

- existing shared summary/detail fields for transcript-normalizable concepts
- a new typed provider-specific `openclaw` detail payload for everything else
- a new `OpenClaw` tab in the conversation viewer as the first UI destination for the richer data

This approach matches the current architecture while maximizing processed local data.

## Source-Of-Truth Split

OpenClaw local storage should be treated as four source classes with different roles.

### 1. Transcript Artifacts

Canonical source for conversation event history:

- live `*.jsonl`
- archived `*.jsonl.reset.*`
- archived `*.jsonl.deleted.*`
- any future transcript siblings following the same family pattern

These own:

- message order
- message content
- tool calls and tool results
- model changes
- thinking-level changes
- compaction events
- branch summaries
- transcript-only custom events

### 2. Session Store

Canonical source for mutable session metadata:

- `~/.openclaw/agents/<agentId>/sessions/sessions.json`

This owns:

- `sessionKey`
- current session file/id linkage
- routing labels
- origin and delivery metadata
- chat type and display metadata
- toggles and overrides
- token counters
- compaction and memory-flush bookkeeping
- `skillsSnapshot`
- `systemPromptReport`

### 3. Memory Store

Supplemental storage/index diagnostics:

- `~/.openclaw/memory/main.sqlite`

This is not conversation history. It should be used for:

- file metadata
- chunk counts
- source/path coverage
- embedding cache counts
- exact, confidence-labeled workspace linkage only when an indexed file path shares a stable prefix with transcript `cwd` or `systemPromptReport.workspaceDir`

First-pass restriction:

- do not claim per-conversation memory attribution from heuristics alone
- do not compute inferred per-conversation chunk totals unless an exact file/path join exists
- if no exact join exists, render the memory store as global OpenClaw memory metadata only

### 4. Auxiliary Provenance

Optional supporting context under `~/.openclaw`, for example:

- config files
- config-audit logs
- cron job state
- device pairing state

These should only be surfaced when they directly explain a conversation behavior or provenance question.

## Conversation Identity And Stitching

The first pass should move from a one-file-one-conversation model to a session-family model.

### Canonical identity

- project path: `openclaw:agent:<agentId>`
- session id: deterministic canonical session id
- provider: `openclaw`

### Canonical session-id algorithm

The first pass must produce exactly one stable `(project_path, session_id)` identity for each routed OpenClaw conversation.

Tie-breaker order:

1. use the `session.id` from the transcript header when present
2. otherwise use the live transcript filename stem
3. otherwise use the `sessionId` from the matched `sessions.json` entry
4. otherwise treat the artifact as unroutable and exclude it from conversation detail/list routes

Agent tie-breaker order:

1. use `session.agentId` from the transcript header when present
2. otherwise use the agent directory name

Family-building rules:

- the canonical route is always anchored to one primary live transcript artifact
- `sessions.json` rows and archived transcript siblings may enrich that route
- enrichment artifacts never create alternate routed identities for the same primary conversation
- if an archive cannot be attached confidently to a routed conversation, it does not become a second route for the same family in the first pass

### Matching rules

- index transcripts by discovered file path and effective session id
- index `sessions.json` entries by:
  - current `sessionId`
  - `sessionFile`
  - session key
- build a stitched OpenClaw session family containing:
  - the active transcript
  - related archived transcript variants
  - at most one canonical `sessions.json` entry chosen by deterministic precedence:
    - exact `sessionFile` match
    - exact `sessionId` match
    - same agent plus strongest session-key/path evidence
  - a summarized memory-store snapshot

### Archive handling

- attach `*.reset.*` and `*.deleted.*` artifacts to the active family when linkage is confident via filename, explicit session file path, or matching session id
- when linkage is not confident, preserve them in discovery but defer them from routed conversation APIs in the first pass
- expose attached archives in the OpenClaw tab as lineage and artifact inventory, not as merged message history by default

First-pass scope rule:

- unattached archives are discovery-time preserved only
- they are not exposed as synthetic conversation rows and do not require a separate UI surface in this phase

## Contract Design

Keep the shared `ConversationDetailResponse` as the portable baseline and add a provider-specific detail field.

### Shared contract remains responsible for

- normalized message list
- total usage shown in the main header
- model
- reasoning effort
- failed tool-call counts
- message/tool summaries
- any context metrics that already map to shared abstractions

### Provider-specific field

Make `provider` explicit on conversation detail responses and add an optional `provider_detail` object.

Wire shape:

- `provider`: required on detail and summary responses
- `provider_detail`: optional discriminated union, omitted entirely when absent
- non-OpenClaw providers omit `provider_detail`
- OpenClaw detail returns:
  - `provider_detail.kind = "openclaw"`
  - `provider_detail.openclaw = { ...typed payload... }`

This avoids adding a top-level `openclaw` field to every provider payload while keeping the backend and frontend type boundaries explicit.

### Recommended OpenClaw provider detail sections

#### `artifact_inventory`

- live transcript path
- archived transcript paths
- `sessions.json` path
- `memory/main.sqlite` path
- modified times
- file sizes
- artifact status such as `live`, `reset_archive`, `deleted_archive`, `orphaned`

#### `session_store`

- `sessionKey`
- `sessionId`
- `sessionFile`
- `updatedAt`
- `chatType`
- `provider`
- `displayName`
- `subject`
- `room`
- `space`
- `deliveryContext`
- `origin`
- `thinkingLevel`
- `verboseLevel`
- `reasoningLevel`
- `elevatedLevel`
- `sendPolicy`
- `providerOverride`
- `modelOverride`
- `authProfileOverride`
- token counters
- compaction and memory-flush bookkeeping

#### `skills`

- `skillsSnapshot.version`
- prompt text or prompt summary
- declared skills
- resolved skills
- required environment metadata
- skill source and resolved file path
- transcript-derived usage signals where detectable

#### `system_prompt`

- `systemPromptReport`
- workspace dir
- provider/model at bootstrap
- sandbox mode
- bootstrap char budgets
- truncation state
- injected workspace files

#### `transcript_diagnostics`

- session header
- model-change sequence
- thinking-level-change sequence
- custom events
- compaction events
- branch summary events
- unmatched tool results
- repeated tool results
- parent/branch linkage
- archive lineage

#### `usage_reconciliation`

- latest authoritative transcript usage snapshot
- latest `sessions.json` counters
- mismatches between transcript/store totals
- explicit transcript cost vs estimated cost vs unknown cost
- store `contextTokens` as a secondary estimate

#### `memory_store`

- sqlite file metadata
- table inventory
- row counts where cheap to compute
- chunk/file/source counts
- embedding cache counts
- exact workspace linkage with confidence labels only

#### `raw`

- raw session-store entry
- raw session header
- raw diagnostic events
- raw memory summary rows

## UI Design

### First-pass tab strategy

Add an `OpenClaw` tab first, then promote concepts into shared tabs when the mapping is clean.

Tab gating rules:

- the `OpenClaw` tab is rendered only when `provider === "openclaw"` and `provider_detail.kind === "openclaw"`
- non-OpenClaw providers do not render an empty placeholder tab
- canonical conversation URLs remain unchanged except for permitting the new tab value

### OpenClaw tab section order

1. Session Overview
2. Routing And Origin
3. Skills And Prompt Bootstrap
4. Usage Reconciliation
5. Transcript Diagnostics
6. Memory Store
7. Artifact Inventory
8. Raw OpenClaw Payloads

### Shared tab rollout rules

#### Messages

- continue rendering normalized transcript messages
- later consider visual markers for compaction/branch events if they render cleanly

#### Context

- promote transcript-derived usage-step data when it maps to the current context model
- show store `contextTokens` only as a secondary estimate, never as the main truth

#### Failed Calls

- improve coverage by preserving unmatched and archived tool-result failures when attributable

#### Raw

- evolve from transcript-only raw output into a stitched OpenClaw raw bundle

#### Sub-agents

- remain empty unless a trustworthy OpenClaw subagent/thread concept appears in artifacts

## Backend Changes

### Discovery

Replace the current OpenClaw filesystem adapter with a richer discovery layer that can enumerate:

- live transcripts
- archived transcripts
- session-store files
- memory-store file metadata

The adapter should expose enough metadata to build stitched session families without forcing transcript parsing to do file-system discovery itself.

### Parsing

Expand OpenClaw payload parsing to preserve more event types and more fields from known events.

First-pass event matrix:

- `session`
  - retain `id`, `cwd`, `timestamp`, `parentSession`, `agentId`, title-like metadata, and unknown extras in raw
- `message`
  - retain role, content blocks, usage, cost, model/provider/api metadata, stop reason, tool linkage, and unknown extras in raw
  - OpenClaw tool results are derived from `message` events whose role is `tool` or `toolResult`; there is no separate first-pass top-level tool-result event type
  - retain `toolCallId`, `toolName`, `isError`, result content, and ordering information needed to classify matched, unmatched, and repeated tool results
- `model_change`
  - retain provider, model id, timestamp
- `thinking_level_change`
  - retain thinking level, timestamp
- `custom`
  - retain custom type, data payload, timestamp
- `custom_message`
  - retain payload in provider detail/raw even if not promoted into normalized messages in the first pass
- `compaction`
  - retain compaction summary fields and timestamp
- `branch_summary`
  - retain branch linkage/summary fields and timestamp

Requirements:

- parse the explicit event matrix above in the first pass
- preserve unknown/custom events in provider detail
- do not silently discard structured fields such as `cost`, `api`, nested metadata, or custom payload objects
- treat everything outside the event matrix as opaque unknown events captured in raw/provider detail rather than as required normalized behavior

### Discovery and polling limits

First-pass performance rules:

- normal conversation-list polling reuses cached OpenClaw discovery results
- polling may rescan known `sessions/` directories and `sessions.json` files by mtime only
- normal polling does not rewalk archive trees beyond known `sessions/` directories
- normal polling does not open `memory/main.sqlite`
- `memory/main.sqlite` may be inspected only when:
  - an OpenClaw conversation detail view is requested
- attached archive metadata should be cached off discovery results so detail views do not trigger full rediscovery unless source mtimes changed

### Conversation shaping

Summary shaping should continue to derive portable fields from transcript data, but detail shaping should attach the stitched provider-specific payload.

### Schema and client types

Add corresponding typed backend schema and frontend client/schema/normalize support for the provider-specific OpenClaw detail object.

Frontend implications to make explicit:

- extend the detail schema, normalized types, and tab enum to include the new provider detail and `openclaw` tab value
- preserve backward compatibility for existing detail consumers by making `provider_detail` optional
- require route handling tests for the new tab value on canonical conversation routes

## Testing Strategy

Add fixtures and tests for:

- live transcript only
- transcript plus `sessions.json` enrichment
- reset archive family
- deleted archive family
- unmatched tool result
- repeated tool result
- custom and compaction events
- transcript/store token mismatch
- memory-store summary extraction
- optional missing artifacts

UI/client tests should verify:

- `OpenClaw` tab appears for OpenClaw conversations
- `OpenClaw` tab does not appear for non-OpenClaw providers
- provider detail survives normalization
- raw and provider-specific sections render without crashing when some subsections are missing
- canonical conversation routes accept the new tab without regressing existing tabs
- list/detail refresh follows the first-pass polling rules:
  - polling reuses cached discovery results
  - polling rescans only known session directories and `sessions.json` by mtime
  - polling does not open `memory/main.sqlite`

## Risks And Mitigations

### Risk: archive linkage is ambiguous

Mitigation:

- attach only when confidence is high
- otherwise preserve in discovery only and defer from routed conversation APIs in the first pass

### Risk: session-store and transcript totals disagree

Mitigation:

- never silently choose one without surfacing the mismatch
- keep transcript totals authoritative for rendered conversation usage

### Risk: memory-store inspection becomes expensive

Mitigation:

- keep first-pass memory queries shallow and summary-oriented
- avoid loading embeddings or large chunk payloads

### Risk: provider-specific payload grows quickly

Mitigation:

- keep it sectioned and typed
- promote stable cross-provider concepts into shared tabs only when justified

## Acceptance Criteria

- conversation summaries and details expose `provider` explicitly for OpenClaw routes
- OpenClaw detail responses expose a typed `provider_detail.kind = "openclaw"` payload
- OpenClaw conversations expose a dedicated `OpenClaw` tab
- the `OpenClaw` tab is rendered only for OpenClaw conversations
- the OpenClaw tab shows stitched data from transcripts, `sessions.json`, archives, and `memory/main.sqlite` when available
- shared conversation headers and messages continue to work for OpenClaw
- attached archived transcript artifacts are surfaced in provider detail
- unattached archives are preserved in discovery state only and are not exposed through routed conversation detail in the first pass
- `skillsSnapshot` and `systemPromptReport` are visible in the UI
- transcript/store usage mismatches are surfaced explicitly
- canonical routing for `(project_path, session_id)` remains deterministic and stable for OpenClaw conversations
- first-pass memory-store rendering uses only exact or explicitly confidence-labeled joins
- normal polling reuses cached discovery results, rescans only known session directories plus `sessions.json` by mtime, and does not open `memory/main.sqlite`
- missing optional artifacts degrade safely without breaking conversation detail rendering
