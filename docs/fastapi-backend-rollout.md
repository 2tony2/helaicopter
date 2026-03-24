# FastAPI Backend Rollout

## Migration Result

The Next.js API surface has been removed from the runtime path. Helaicopter now runs as:

- A Next.js frontend in [`src/`](/Users/tony/Code/helaicopter/src)
- A FastAPI backend in [`python/helaicopter_api/`](/Users/tony/Code/helaicopter/python/helaicopter_api)
- A shared frontend client layer in [`src/lib/client/`](/Users/tony/Code/helaicopter/src/lib/client) that calls FastAPI routes directly

The backend split is complete enough for day-to-day development:

- `src/app/api` route handlers are removed.
- FastAPI owns health, OpenAPI, and application routers.
- Frontend endpoint builders stay relative unless `NEXT_PUBLIC_API_BASE_URL` is configured.
- [`src/lib/client/normalize.ts`](/Users/tony/Code/helaicopter/src/lib/client/normalize.ts) still accepts both legacy camelCase payloads and current snake_case FastAPI responses so cached fixtures continue to load during cleanup.

## Local Developer Runbook

Install both dependency stacks once per checkout:

```bash
npm install
uv sync --group dev
```

The default development command starts both processes together and cleans up stale repo-local dev servers first:

```bash
npm run dev
```

Default local ports:

- Frontend: `http://localhost:3000`
- Backend: `http://127.0.0.1:30000`

If you want the split commands:

```bash
npm run dev:web
npm run api:dev
```

Override the frontend target if the backend is not on the default origin:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:30000 npm run dev
```

Useful backend environment overrides:

```bash
HELA_PROJECT_ROOT=/path/to/helaicopter
HELA_CLAUDE_DIR=/path/to/.claude
HELA_CODEX_DIR=/path/to/.codex
HELA_OATS_RUNTIME_DIR=/path/to/.oats/runtime
```

Quick sanity checks:

```bash
curl http://127.0.0.1:30000/health
curl http://127.0.0.1:30000/gateway/direction
open http://127.0.0.1:30000/openapi.json
```

## Gateway Direction

FastAPI is the single backend gateway for the runtime platform:

- The Next.js frontend calls FastAPI directly rather than talking to DuckDB or repo-local artifacts on its own.
- The legacy repo-local Oats runtime remains available under `/orchestration/oats` as a compatibility and inspection surface.
- SQLite-backed app metadata remains the primary backend read/write store.
- DuckDB remains inspection-only and is intentionally surfaced through the Databases API rather than treated as a peer application backend.

Use `/gateway/direction` when you need the backend-owned summary of those boundaries.

## Verification Coverage

Run the full handoff validation set before merging backend rollout work:

```bash
npm run lint
npm run build
uv run --group dev pytest -q
npm run api:openapi
```

What these prove:

- `npm run lint` checks the frontend TypeScript/React surface and client call-sites.
- `npm run build` proves the Next.js frontend still compiles against the FastAPI-backed client layer.
- `uv run --group dev pytest -q` covers the FastAPI routers, backend services, rollout split checks, and Python-side helpers.
- `npm run api:openapi` refreshes the committed OpenAPI snapshots under `public/openapi/`.

## OpenAPI Artifact Workflow

The repo keeps generated OpenAPI artifacts in `public/openapi/` so the frontend can expose stable download links without depending on a running backend.

Regenerate them after any backend route or schema change:

```bash
npm run api:openapi
```

Expected outputs:

- `public/openapi/helaicopter-api.json`
- `public/openapi/helaicopter-api.yaml`

Use those committed snapshots for review and diffing, and compare them against the configured backend origin plus `/openapi.json` when validating a configured live local server.

## Migration Notes

- Keep the compatibility normalization path until cached fixtures and any persisted camelCase responses are retired.
- README is the canonical onboarding doc for running Next.js plus FastAPI locally.
- This document is the rollout record for the backend split and the required verification commands.
- Database status contract debt still intentionally preserved after the type-system rollout:
  - `duckdb` (canonical field) while the parser still accepts `legacyDuckdb`
  - `analyticsReadBackend`
  - `conversationSummaryReadBackend`
- Retirement target for those database labels: `2026-06-30`. Do not add more aliases or helper shims around them before that cleanup lands.
