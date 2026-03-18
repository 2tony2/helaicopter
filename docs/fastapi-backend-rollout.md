# FastAPI Backend Rollout

## Migration Result

The Next.js API surface has been removed from the runtime path. Helaicopter now runs as:

- A Next.js frontend in [`src/`](/Users/tony/Code/helaicopter/src)
- A FastAPI backend in [`python/helaicopter_api/`](/Users/tony/Code/helaicopter/python/helaicopter_api)
- A shared frontend client layer in [`src/lib/client/`](/Users/tony/Code/helaicopter/src/lib/client) that calls FastAPI routes directly

The backend split is complete enough for day-to-day development:

- `src/app/api` route handlers are removed.
- FastAPI owns health, OpenAPI, and application routers.
- Frontend endpoint builders default to `http://localhost:8000` when the browser is on `http://localhost:3000`.
- [`src/lib/client/normalize.ts`](/Users/tony/Code/helaicopter/src/lib/client/normalize.ts) still accepts both legacy camelCase payloads and current snake_case FastAPI responses so cached fixtures continue to load during cleanup.

## Local Developer Runbook

Install both dependency stacks once per checkout:

```bash
npm install
uv sync --group dev
```

Run the local development pair in separate terminals:

```bash
# Terminal 1
npm run dev

# Terminal 2
npm run api:dev
```

Default local ports:

- Frontend: `http://localhost:3000`
- Backend: `http://127.0.0.1:8000`

Override the frontend target if the backend is not on the default origin:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev
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
curl http://127.0.0.1:8000/health
open http://127.0.0.1:8000/openapi.json
```

## Verification Coverage

Run the full handoff validation set before merging backend rollout work:

```bash
npm run lint
npm run build
uv run --group dev pytest -q
```

What these prove:

- `npm run lint` checks the frontend TypeScript/React surface and client call-sites.
- `npm run build` proves the Next.js frontend still compiles against the FastAPI-backed client layer.
- `uv run --group dev pytest -q` covers the FastAPI routers, backend services, rollout split checks, and Python-side helpers.

## Migration Notes

- Keep the compatibility normalization path until cached fixtures and any persisted camelCase responses are retired.
- README is the canonical onboarding doc for running Next.js plus FastAPI locally.
- This document is the rollout record for the backend split and the required verification commands.
