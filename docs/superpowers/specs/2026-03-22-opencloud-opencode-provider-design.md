# OpenCloud / OpenCode Provider Design

## Goal

Add a new first-class provider for the feature branch's "OpenCloud" scope by integrating real OpenCode conversation data into Helaicopter so sessions, tool calls, and token usage appear alongside Claude, Codex, and OpenClaw data.

## What OpenCloud Is

There is no concrete local or upstream product artifact named `OpenCloud` in this repo or on this machine. The branch name is `feat/opencloud-conversations-toolcalls-usage`, but the installed upstream product and local data source are OpenCode:

- official docs and SDK types use the `OpenCode` name
- the local install exists at `~/.opencode` and `~/.local/share/opencode`
- persistent session data lives in `~/.local/share/opencode/opencode.db`

This implementation therefore treats "OpenCloud" as the feature label and integrates the real OpenCode data source.

## Context

The repo already supports:

- Claude via JSONL files in `~/.claude`
- Codex via JSONL plus SQLite metadata in `~/.codex`
- OpenClaw via JSONL artifacts in `~/.openclaw`

OpenCode introduces a fourth shape:

- SQLite database at `~/.local/share/opencode/opencode.db`
- `session` rows for thread metadata
- `message` rows for user/assistant metadata
- `part` rows for message content, tool calls, reasoning, and step token snapshots

The typed SDK confirms that OpenCode models:

- assistant message-level token totals
- tool parts with input, output, timing, and error state
- step-finish parts with cost and token counters
- parent/child session relationships

## Requirements

- Discover OpenCode sessions from the local SQLite database
- Normalize them into existing conversation summary/detail contracts
- Surface tool calls and tool results in the conversation viewer
- Surface token usage and reasoning totals in summaries and detail views
- Preserve provider provenance separately from model/vendor metadata
- Extend analytics, exports, filters, and route resolution for the new provider

## Recommended Approach

Add a dedicated OpenCode-backed provider keyed as `opencloud` in repo contracts, while documenting that it reads OpenCode artifacts.

Why this shape:

- it matches the branch and requested feature name
- it avoids renaming a large existing provider vocabulary mid-branch
- it keeps the integration explicit in analytics and UI
- it leaves room for a later rename to `opencode` if the product vocabulary is standardized

## Architecture

### Storage Adapter

Create a readonly OpenCode store adapter that:

- opens `opencode.db` in readonly mode
- lists sessions ordered by update time
- fetches session metadata, messages, and parts for one session
- tolerates the database being absent or temporarily locked

### Provider Identity

Introduce `opencloud` as a first-class provider in repo vocab and frontend types.

Identity rules:

- `claude` = Claude local artifacts
- `codex` = Codex local artifacts
- `openclaw` = OpenClaw local artifacts
- `opencloud` = OpenCode local SQLite artifacts

### Project Identity

Use session directory as the canonical grouping key:

- project path: `opencloud:<directory>`
- project name: display-friendly path derived from the directory

This matches how OpenCode sessions are already rooted to a project/worktree in the database.

### Summary Extraction

Build conversation summaries from:

- `session` row for title, timestamps, parent linkage, directory
- earliest user message and text part for `first_message`
- latest assistant message for model/provider/agent metadata
- latest `step-finish` part for authoritative tokens and cost
- all `tool` parts for tool counts and failure counts

### Detail Extraction

Build normalized messages by joining:

- message metadata
- ordered parts for each message

Map parts:

- `text` -> text block
- `reasoning` -> thinking block
- `tool` -> tool call block with result/error state
- `subtask` -> tool-call style block for spawned subtask visibility when possible

Use assistant message token totals where available, but prefer the adjacent `step-finish` part as the authoritative per-step usage because it is explicit and already split into input/output/reasoning/cache fields.

### Analytics And Export

Treat OpenCloud as a fourth provider bucket everywhere provider-specific aggregates exist.

Export behavior:

- include OpenCloud rows in historical export iteration
- preserve `provider = opencloud`
- preserve source path as the SQLite-backed synthetic source identifier

## Risks

- OpenCode databases can be locked by a running CLI, so reads must use readonly URI mode
- some assistant messages may have no text parts and only tool activity
- some sessions may have no finished step snapshot yet, so totals must degrade safely

## Acceptance Criteria

- OpenCloud sessions appear in `/conversations`
- OpenCloud detail pages render text, reasoning, tool calls, and token usage
- Provider filters and analytics include OpenCloud
- Export/indexing preserves OpenCloud provenance
- UI verification confirms the new provider is visible and navigable
