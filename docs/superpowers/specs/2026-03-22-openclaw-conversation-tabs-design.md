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
- likely workspace linkage to the conversation

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
- session id: effective transcript/session id
- provider: `openclaw`

### Matching rules

- index transcripts by discovered file path and effective session id
- index `sessions.json` entries by:
  - current `sessionId`
  - `sessionFile`
  - session key
- build a stitched OpenClaw session family containing:
  - the active transcript
  - related archived transcript variants
  - matching `sessions.json` entry or entries
  - a summarized memory-store snapshot

### Archive handling

- attach `*.reset.*` and `*.deleted.*` artifacts to the active family when linkage is confident via filename, explicit session file path, or matching session id
- when linkage is not confident, preserve them as unattached OpenClaw artifacts rather than dropping them
- expose attached archives in the OpenClaw tab as lineage and artifact inventory, not as merged message history by default

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

Add an optional provider-specific payload on conversation detail responses, discriminated by provider. For OpenClaw, expose a typed `openclaw` object.

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
- likely workspace linkage to transcript `cwd` or `systemPromptReport.workspaceDir`

#### `raw`

- raw session-store entry
- raw session header
- raw diagnostic events
- raw memory summary rows

## UI Design

### First-pass tab strategy

Add an `OpenClaw` tab first, then promote concepts into shared tabs when the mapping is clean.

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

Requirements:

- parse all known event types currently seen locally and documented upstream
- preserve unknown/custom events in provider detail
- do not silently discard structured fields such as `cost`, `api`, nested metadata, or custom payload objects

### Conversation shaping

Summary shaping should continue to derive portable fields from transcript data, but detail shaping should attach the stitched provider-specific payload.

### Schema and client types

Add corresponding typed backend schema and frontend client/schema/normalize support for the provider-specific OpenClaw detail object.

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
- provider detail survives normalization
- raw and provider-specific sections render without crashing when some subsections are missing

## Risks And Mitigations

### Risk: archive linkage is ambiguous

Mitigation:

- attach only when confidence is high
- otherwise preserve as unattached provider artifacts

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

- OpenClaw conversations expose a dedicated `OpenClaw` tab
- the OpenClaw tab shows stitched data from transcripts, `sessions.json`, archives, and `memory/main.sqlite` when available
- shared conversation headers and messages continue to work for OpenClaw
- archived transcript artifacts are discovered and surfaced in provider detail
- `skillsSnapshot` and `systemPromptReport` are visible in the UI
- transcript/store usage mismatches are surfaced explicitly
- missing optional artifacts degrade safely without breaking conversation detail rendering
