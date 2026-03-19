# Helaicopter

A local Next.js app for browsing your [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://developers.openai.com/codex/) conversations, plans, and token/cost analytics. Reads directly from `~/.claude/` and `~/.codex/` — no data leaves your machine.

## Quick Start

```bash
# Clone and install
git clone https://github.com/curative/helaicopter.git
cd helaicopter
npm install
uv sync --group dev

# Start the frontend and FastAPI backend together
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Integrated Tooling

This repo now also vendors the `overnight-oats` orchestration CLI as the `oats` Python package. That keeps the repo-local agent workflow tooling next to the app and database code instead of split across multiple repositories.

```bash
# inspect a run spec
uv run oats plan examples/sample_run.md

# primary orchestration path: register and launch through Prefect
uv run oats prefect deploy examples/prefect_native_oats_orchestration_run.md
uv run oats prefect run examples/prefect_native_oats_orchestration_run.md

# legacy compatibility path: local runtime state under .oats/runtime
uv run oats run examples/sample_run.md
```

The default repo policy lives in `.oats/config.toml`, sample run specs live in `examples/`, and the Python implementation lives in `python/oats/`.
Use [`docs/prefect-local-ops.md`](/Users/tony/Code/helaicopter/docs/prefect-local-ops.md) for local control-plane setup and [`docs/oats-prefect-cutover.md`](/Users/tony/Code/helaicopter/docs/oats-prefect-cutover.md) for the cutover and rollback checklist.

## Requirements

- **Node.js** 20+ (22+ recommended)
- **npm** 10+
- **Python** 3.13+
- **uv** 0.6+
- **Claude Code** and/or **Codex** installed (the app reads from `~/.claude/` and `~/.codex/`)

## Local Development

The default local dev command starts both processes and cleans up stale Helaicopter dev servers first:

```bash
npm run dev
```

- The Next.js frontend serves on `http://localhost:3000`.
- The FastAPI backend serves on `http://127.0.0.1:30000`.
- `npm run dev` starts both servers, kills stale repo-local `next dev` and `uvicorn` processes, and sets `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:30000` unless you override it yourself.
- When `NEXT_PUBLIC_API_BASE_URL` is unset and the frontend runs on `localhost` or `127.0.0.1`, [`src/lib/client/endpoints.ts`](/Users/tony/Code/helaicopter/src/lib/client/endpoints.ts) automatically targets port `30000`.
- If you want the frontend to use a different backend origin, set `NEXT_PUBLIC_API_BASE_URL` before starting `npm run dev`.

If you want to run the processes separately:

```bash
npm run dev:web
npm run api:dev
```

Backend settings are read from `HELA_*` environment variables in [`python/helaicopter_api/server/config.py`](/Users/tony/Code/helaicopter/python/helaicopter_api/server/config.py). The most useful local overrides are:

```bash
HELA_PROJECT_ROOT=/path/to/helaicopter
HELA_CLAUDE_DIR=/path/to/.claude
HELA_CODEX_DIR=/path/to/.codex
HELA_OATS_RUNTIME_DIR=/path/to/.oats/runtime  # legacy compatibility surface
```

Useful local checks:

```bash
curl http://127.0.0.1:30000/health
open http://127.0.0.1:30000/openapi.json
```

The migration runbook and validation checklist live in [`docs/fastapi-backend-rollout.md`](/Users/tony/Code/helaicopter/docs/fastapi-backend-rollout.md).

## Features

### Analytics (Homepage)
The homepage shows a full analytics dashboard with stats cards, cost breakdown, daily usage charts, tool usage, model breakdown, and conversations per day — all scoped to a selectable date range (7d / 14d / 30d / 90d / All). A **provider filter** (All / Claude / Codex) lets you scope analytics to a single provider.

### Provider Filter
A toggle on both the analytics page and conversations list lets you switch between:
- **All** — shows both Claude and Codex data
- **Claude** — Claude Code conversations only
- **Codex** — OpenAI Codex conversations only

### Conversations

- Filterable list with search, project filter, date range, and provider filter
- **Color-coded model badges**: Claude models in red, GPT/OpenAI models in blue
- Each card shows: first message, project, branch, model, message count, tool calls, sub-agent count, task count, total context tokens, and estimated cost
- **Conversation Viewer** with tabs:
  - **Messages** — Full message thread with collapsible thinking blocks and tool call/result pairs
  - **Context** — Per-tool and per-category token/cost breakdown with stacked bar chart, category filter, and click-to-expand step details
  - **Sub-agents** — List of spawned sub-agents with description, type, and inline viewer
  - **Tasks** — Task list for the session
  - **Raw** — Full scrollable JSON data with download button (no truncation)

#### Context Analytics
Per-tool and per-step token attribution with stacked bar charts and category filtering.

#### Sub-agents
Inline viewer for Claude Code sub-agent conversations with full message replay.

### Token Display
Token counts are split into color-coded badges with individual tooltips:
- **Input** (blue) — base input tokens
- **Output** (green) — output tokens
- **Cache write** (yellow, Claude only) — prompt cache creation
- **Cache read / Cached input** (purple) — prompt cache hits or discounted cached input for OpenAI/Codex

Plus a **cost badge** (amber) showing estimated dollar cost with full breakdown on hover.

### Plans
Browse and view saved implementation plans from `~/.claude/plans/` rendered as markdown.

### Pricing Reference

Dedicated page documenting all API pricing used for cost estimates. All cost estimates assume API pricing.

**Claude API pricing:**
- Per-model token rates (input, output, 5m cache write, 1h cache write, cache read)
- Prompt caching multipliers (1.25x / 2.0x / 0.1x)
- Long context premium (>200K tokens: 2x input, 1.5x output)
- Tool overhead tokens (bash 245, text editor 700, etc.)
- Other modifiers (fast mode, batch API, data residency)

**OpenAI API pricing:**
- Per-model token rates (input, output, cached input) for GPT-5.4, GPT-5.2, GPT-5.1, GPT-5, GPT-5-mini, o3, o4-mini
- Sources: [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing/) and [Codex Pricing](https://developers.openai.com/codex/pricing/)

## Runtime Architecture

- **SQLite** stores app-local metadata, refresh bookkeeping, evaluations, and historical detail tables.
- **ClickHouse** is the primary analytics and event store for warehouse-style reads.
- **DuckDB** is no longer on the primary serving path. If present, it is only a legacy/local inspection artifact surfaced on the Databases page.

## Frontend/Backend Split

- [`src/`](/Users/tony/Code/helaicopter/src) is frontend-only code: App Router pages, React components, hooks, and HTTP clients.
- [`python/helaicopter_api/`](/Users/tony/Code/helaicopter/python/helaicopter_api) owns the backend surface: FastAPI app creation, dependency wiring, routers, and application services.
- [`python/oats/`](/Users/tony/Code/helaicopter/python/oats) contains the orchestration CLI packaged alongside the backend code.
- The removed Next.js route-handler layer is no longer part of the runtime. Frontend callers now hit FastAPI routes directly.

## How It Works

### Data Sources

Helaicopter reads from two local directories:

**Claude Code** (`~/.claude/`):
```
~/.claude/
├── projects/           # Conversation JSONL files per project
│   └── <encoded-path>/
│       ├── <session-uuid>.jsonl
│       └── <session-uuid>/
│           └── subagents/
│               └── agent-<7hex>.jsonl
├── plans/              # Saved plans as markdown
├── tasks/              # Task data per session
└── history.jsonl       # Command history
```

**Codex** (`~/.codex/`):
```
~/.codex/
├── sessions/           # Conversation JSONL files organized by date
│   └── YYYY/MM/DD/
│       └── rollout-<timestamp>-<uuid>.jsonl
├── state_5.sqlite      # Thread metadata (title, git info, tokens)
└── history.jsonl       # Command history
```

Codex conversations are identified by a `codex:` prefix on the project path and integrated seamlessly alongside Claude conversations in all views.

### Performance

- **Streaming JSONL parser** — handles 200MB+ conversation files without loading into memory
- **File mtime pre-filter** — skips files outside the date range before parsing (the key optimization)
- **In-memory LRU cache** — keyed on file path + mtime, auto-invalidates on changes
- **Default 7-day window** — loads ~100-150 conversations instead of 300+ for all time
- **SWR client caching** — no refetch on focus, shared cache across components
- **SQLite enrichment** — Codex thread metadata (git branch, title) read from SQLite for fast lookups

### Cost Calculation

Costs are estimated per-conversation using the actual model from the conversation data:
- Matched to published API pricing via model ID (Claude and OpenAI models)
- Claude: uses 5-minute prompt cache write rates (Claude Code default)
- OpenAI: cache writing is free, cached input is discounted
- Detects long context premium for Claude (>200K input tokens = 2x input, 1.5x output)
- Tool overhead tokens are already included in the API's `input_tokens` count

## Project Structure

```
python/
├── helaicopter_api/               # FastAPI backend and application services
└── oats/                          # Orchestration CLI package
src/
├── app/                           # Frontend routes and layouts only
│   ├── layout.tsx                 # Root layout with sidebar
│   ├── page.tsx                   # Analytics homepage
│   ├── conversations/
│   │   ├── page.tsx               # Conversation list
│   │   └── [projectPath]/[sessionId]/page.tsx
│   ├── plans/
│   │   ├── page.tsx               # Plans list
│   │   └── [slug]/page.tsx        # Plan viewer
│   └── pricing/page.tsx           # Pricing reference
├── components/                    # React UI building blocks
├── hooks/                         # SWR data hooks
└── lib/
    ├── client/                    # FastAPI endpoint builders, fetchers, mutations
    ├── constants.ts               # Shared pricing tables
    ├── evaluation-models.ts       # Frontend evaluation form options
    ├── path-encoding.ts           # Project path display helpers
    ├── pricing.ts                 # Cost calculation utilities
    ├── types.ts                   # Frontend data contracts
    └── utils.ts                   # UI helper utilities
```

Compatibility shim: [`src/lib/client/normalize.ts`](/Users/tony/Code/helaicopter/src/lib/client/normalize.ts) still accepts the legacy camelCase Next.js payload shape as well as the FastAPI snake_case schema so cached fixtures and in-flight responses continue to normalize during rollout cleanup.

## Legacy Runtime Structure

The removed Next.js route handlers and their Node-side backend adapters previously lived in `src/`. They are superseded by the FastAPI backend under [`python/helaicopter_api/`](/Users/tony/Code/helaicopter/python/helaicopter_api), so `src/` now stays focused on frontend code.

## Historical Layout

The pre-cutover app structure looked like this:

```
src/
├── app/                           # Frontend pages plus embedded Node API
├── lib/                           # Shared frontend code plus Node data loaders
├── hooks/
└── components/
```
## Tech Stack

- [Next.js 16](https://nextjs.org/) (App Router, Turbopack)
- [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS v4](https://tailwindcss.com/)
- [shadcn/ui](https://ui.shadcn.com/) component patterns
- [Radix UI](https://www.radix-ui.com/) primitives
- [SWR](https://swr.vercel.app/) for data fetching
- [Recharts](https://recharts.org/) for charts
- [better-sqlite3](https://github.com/WiseLibs/better-sqlite3) for Codex SQLite reading
- [react-markdown](https://github.com/remarkjs/react-markdown) + remark-gfm
- [date-fns](https://date-fns.org/) for dates
- [Lucide](https://lucide.dev/) for icons

## Scripts

```bash
npm run dev              # Start Next.js + FastAPI together
npm run dev:web          # Start only the Next.js development server
npm run api:dev          # Start only the FastAPI backend with uvicorn (port 30000)
npm run build            # Production frontend build
npm run start            # Start the production Next.js server
npm run lint             # ESLint
npm run oats -- ...      # Run the packaged orchestration CLI through uv
npm run db:refresh       # Run the Python refresh pipeline
npm run db:migrate:oltp  # Apply OLTP alembic migrations
npm run db:migrate:olap  # Apply OLAP alembic migrations
npm run db:export        # Export parsed data from the repo tooling
```

## Validation

Run the full local validation set before merging FastAPI rollout work:

```bash
npm run lint
npm run build
uv run --group dev pytest -q
```

## Troubleshooting

- If the frontend cannot reach the backend, confirm `npm run dev` or `npm run api:dev` is running and that `NEXT_PUBLIC_API_BASE_URL` points to the correct origin.
- If the backend cannot find local conversation data, set `HELA_CLAUDE_DIR`, `HELA_CODEX_DIR`, or `HELA_PROJECT_ROOT` explicitly.
- If API behavior looks wrong, compare `http://127.0.0.1:30000/openapi.json` against the expected router surface under [`python/helaicopter_api/router/`](/Users/tony/Code/helaicopter/python/helaicopter_api/router).

## License

Internal use only.
