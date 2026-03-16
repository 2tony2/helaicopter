# Ticket 05: Build The Go Live Ingestion Service

## Mission

Add a narrow Go service that tails local LLM conversation logs and writes normalized events into ClickHouse with low latency.

## Architecture Context

- Read `docs/clickhouse-kappa-architecture.md` first.
- Claude logs live under `~/.claude/`; Codex logs live under `~/.codex/`.
- Parsing behavior in `src/lib/jsonl-parser.ts` and `src/lib/codex-jsonl-parser.ts` is the reference for normalization rules.
- This Go service should own ingestion and stream fanout only. Do not replace the Next.js UI server.

## Required Outcome

There is a runnable Go service that watches local session files, normalizes provider-specific events, and batches append-only writes into ClickHouse.

## Requirements

- Add a Go module and service with:
  - filesystem watching for Claude and Codex session files
  - append-only tailing semantics
  - provider-agnostic normalized event envelopes
  - batched ClickHouse writes
  - retry and backpressure handling
- Add startup docs and local run instructions.
- Define the event id and deduplication contract clearly.

## Validation

- New events show up in ClickHouse shortly after source logs change.
- Basic manual testing covers parallel session activity without duplicate ingestion or obvious dropped events.
- Any build or test commands for the Go service are documented and run.

## Runner Contract

- You are already on a runner-created branch based on `main`.
- Do not create or switch branches.
- Do not create PRs or merge anything.
- Implement the ticket end-to-end and run the required validation before finishing.
