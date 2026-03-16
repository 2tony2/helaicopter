# Ticket 06: Add Live Streaming Transport For The UI

## Mission

Replace slow polling-only behavior with push-based updates for analytics and active conversations.

## Architecture Context

- Read `docs/clickhouse-kappa-architecture.md` first.
- `src/hooks/use-conversations.ts` currently polls every 30 seconds for live views.
- The Go ingestion service from the previous ticket should provide enough live change information to support streaming updates.
- The app still needs a safe polling fallback.

## Required Outcome

The UI can receive push-based updates through SSE or WebSockets for analytics invalidation and active conversation changes.

## Requirements

- Add SSE or WebSocket support for:
  - analytics update or invalidation events
  - active conversation update events
- Wire the Next.js app to consume the stream directly or through a small proxy route.
- Preserve polling as a fallback path until the stream path is stable.

## Validation

- Active pages update without waiting for the current 30-second polling interval.
- Disconnect and reconnect behavior is safe.
- The app still works when streaming is unavailable.

## Runner Contract

- You are already on a runner-created branch based on `main`.
- Do not create or switch branches.
- Do not create PRs or merge anything.
- Implement the ticket end-to-end and run the required validation before finishing.
