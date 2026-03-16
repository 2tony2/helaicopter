# Go Live Ingestion Service

This service is the narrow Go boundary for live ingestion and stream fanout. It watches local Claude and Codex session files, normalizes new JSONL lines into the ClickHouse append-only event tables, and exposes an SSE feed of persisted envelopes.

## Requirements

- Go 1.26+
- A reachable ClickHouse instance with the tracked schema applied

## Scope

- Watches `~/.claude/projects/**/*.jsonl`
- Watches `~/.codex/sessions/**/*.jsonl`
- Tails files with append-only semantics
- Normalizes provider-specific lines into:
  - `conversation_events`
  - `message_events`
  - `tool_events`
  - `usage_events`
- Batches writes to ClickHouse over HTTP
- Retries failed batches with exponential backoff
- Applies backpressure by blocking file processing when the ingest queue is full
- Fanouts persisted envelopes on `GET /events` as SSE

It does not replace the Next.js UI server.

## Run

Bootstrap ClickHouse first if needed:

```bash
npm run db:bootstrap:clickhouse:local
```

Then run the ingester:

```bash
npm run go:live-ingestion
```

The default HTTP endpoints are:

- `GET http://127.0.0.1:4318/healthz`
- `GET http://127.0.0.1:4318/stats`
- `GET http://127.0.0.1:4318/events`

The Next.js UI consumes that stream through its same-origin proxy route at `GET /api/live-events`.
By default the proxy targets `HELAICOPTER_GO_INGEST_HTTP_ADDR` and appends `/events`.
Override it explicitly with `HELAICOPTER_GO_INGEST_EVENTS_URL` if the UI should read from a different host.

## Environment

The service reuses the existing ClickHouse env vars:

```bash
HELAICOPTER_CLICKHOUSE_HOST=127.0.0.1
HELAICOPTER_CLICKHOUSE_PORT=8123
HELAICOPTER_CLICKHOUSE_DATABASE=helaicopter
HELAICOPTER_CLICKHOUSE_USER=helaicopter
HELAICOPTER_CLICKHOUSE_PASSWORD=helaicopter
HELAICOPTER_CLICKHOUSE_SECURE=0
HELAICOPTER_CLICKHOUSE_VERIFY_TLS=1
HELAICOPTER_CLICKHOUSE_CONNECT_TIMEOUT_SECONDS=5
HELAICOPTER_CLICKHOUSE_SEND_RECEIVE_TIMEOUT_SECONDS=30
```

Service-specific knobs:

```bash
HELAICOPTER_GO_INGEST_CLAUDE_ROOT=$HOME/.claude
HELAICOPTER_GO_INGEST_CODEX_ROOT=$HOME/.codex
HELAICOPTER_GO_INGEST_HTTP_ADDR=127.0.0.1:4318
HELAICOPTER_GO_INGEST_CHECKPOINT_PATH=var/live-ingestion/checkpoints.json
HELAICOPTER_GO_INGEST_START_POSITION=end
HELAICOPTER_GO_INGEST_BATCH_SIZE=256
HELAICOPTER_GO_INGEST_FLUSH_INTERVAL_MS=500
HELAICOPTER_GO_INGEST_RESCAN_INTERVAL_MS=2000
HELAICOPTER_GO_INGEST_STREAM_REPLAY_CAPACITY=1024
HELAICOPTER_GO_INGEST_QUEUE_CAPACITY=8192
HELAICOPTER_GO_INGEST_MAX_RETRY_DELAY_MS=15000
HELAICOPTER_GO_INGEST_LOG_LEVEL=info
```

`HELAICOPTER_GO_INGEST_START_POSITION=end` is the safe default when ClickHouse already contains historical backfill. Set it to `beginning` only when you intentionally want the Go service to catch up from the start of the watched files.

## Event ID And Dedup Contract

The service is intentionally append-only and crash-safe, not exactly-once.

- Every processed source line gets a deterministic base `event_id`.
- Format: `<provider>:<session_id>:<source_path_hash>:<source_line>`
- Flattened rows derived from that line append a suffix:
  - message row: `...:message:<n>`
  - tool row: `...:tool:<n>`
  - usage row: `...:usage:<n>`
- The SSE stream now emits `id: <event_id>` for every `envelope` event.
- On reconnect, `Last-Event-ID` replays the buffered envelopes that were emitted after the last seen id.
- Checkpoints advance only after ClickHouse acknowledges the batch that contained that line.
- If the process exits after ClickHouse accepted a batch but before the checkpoint file is fsynced, the same lines can be replayed on restart.
- Because the ids are deterministic, replayed rows keep the same `event_id` and can be deduplicated downstream with `event_id`.

Operationally this means:

- Normal operation should not emit duplicates.
- Crash boundaries are at-least-once.
- Consumers that require strict dedupe should treat `event_id` as the idempotency key.
- Stream replay is best-effort and bounded by `HELAICOPTER_GO_INGEST_STREAM_REPLAY_CAPACITY`.

## Checkpoints

Checkpoint state lives in `var/live-ingestion/checkpoints.json` by default. Each file entry stores:

- file identity
- byte offset
- last committed source line number
- provider-specific parser state

Persisting parser state matters for:

- Claude tool calls whose result arrives in a later user event
- Codex assistant turns that only become complete when the later `token_count` delta arrives

## Manual Validation

Build and unit test the Go module:

```bash
cd go/live-ingestion
go test ./...
```

A local smoke test against temp directories:

```bash
tmpdir="$(mktemp -d)"
mkdir -p "$tmpdir/.claude/projects/-tmp-demo" "$tmpdir/.codex/sessions/2026/03/16"
HELAICOPTER_GO_INGEST_CLAUDE_ROOT="$tmpdir/.claude" \
HELAICOPTER_GO_INGEST_CODEX_ROOT="$tmpdir/.codex" \
HELAICOPTER_GO_INGEST_CHECKPOINT_PATH="$tmpdir/checkpoints.json" \
HELAICOPTER_GO_INGEST_START_POSITION=beginning \
npm run go:live-ingestion
```

Then append test lines into both temp session files and verify they arrive in ClickHouse:

```sql
SELECT count() FROM helaicopter.conversation_events WHERE session_id IN ('claude-session', '12345678-1234-1234-1234-123456789abc');
SELECT count(), uniqExact(event_id) FROM helaicopter.conversation_events WHERE session_id IN ('claude-session', '12345678-1234-1234-1234-123456789abc');
```

The second query should show matching counts during a clean run.
