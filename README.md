# Helaicopter

A local Next.js app for browsing your [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Codex](https://developers.openai.com/codex/), and OpenClaw conversations, plans, and token/cost analytics. Reads directly from `~/.claude/`, `~/.codex/`, and `~/.openclaw/` with a local FastAPI backend; no data leaves your machine.

## Quick Start

```bash
git clone https://github.com/curative/helaicopter.git
cd helaicopter
npm install
uv sync --group dev
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Install with Homebrew

Helaicopter now ships a custom Homebrew formula at [`Formula/helaicopter.rb`](Formula/helaicopter.rb).

```bash
brew tap 2tony2/helaicopter https://github.com/2tony2/helaicopter
brew install --HEAD 2tony2/helaicopter/helaicopter
helaicopter serve --open
```

The formula is currently **HEAD-only** because this repository does not publish tagged Homebrew release archives yet. The repository acts as a custom tap, and `brew install --HEAD ...` installs the formula from that tap and gives you a `helaicopter` command on your `PATH`.

Useful commands after install:

```bash
helaicopter bootstrap          # refresh the writable runtime and install app dependencies
helaicopter serve              # run the FastAPI backend and Next.js frontend together
helaicopter serve --open       # start both servers and open the browser
helaicopter paths --pretty     # show the staged Homebrew copy and the writable runtime directory
brew services start helaicopter
brew services stop helaicopter
```

## How Homebrew Works Here

This repository is a mixed **Next.js + FastAPI** app, not a single prebuilt binary. That matters for Homebrew:

- Homebrew installs the formula, plus system-level runtime dependencies: `node`, `python@3.13`, and `uv`.
- The formula stages the repository into Homebrew’s read-only `libexec` area and installs a `helaicopter` launcher command.
- On first run, the launcher copies the staged source into a user-writable runtime directory, runs `npm install --omit=dev`, runs `uv sync --frozen`, and builds the frontend with `npm run build`.
- After bootstrap, `helaicopter serve` starts the FastAPI backend on `http://127.0.0.1:30000` and the Next.js frontend on `http://127.0.0.1:3000`.

The writable runtime directory defaults to:

- `~/Library/Application Support/Helaicopter` on macOS
- `$XDG_DATA_HOME/helaicopter` when `XDG_DATA_HOME` is set
- `~/.local/share/helaicopter` everywhere else

You can override that location with `HELAICOPTER_HOME=/custom/path` or `helaicopter --runtime-root /custom/path ...`.

Why this design instead of a fully vendored Homebrew formula? Homebrew formula builds run in a constrained environment, and this repo spans two package ecosystems. The formula therefore handles the system prerequisites and launcher, while the launcher performs the mutable app bootstrap in a normal writable directory.

## Requirements

- **Node.js** 20+ (22+ recommended)
- **npm** 10+
- **Python** 3.13+
- **uv** 0.6+
- **Claude Code**, **Codex**, and/or **OpenClaw** installed

## Local Development

The default local dev command starts both the Next.js frontend and the FastAPI backend:

```bash
npm run dev
```

- The frontend serves on `http://localhost:3000`.
- The FastAPI backend serves on `http://127.0.0.1:30000`.
- `npm run dev` sets `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:30000` unless you override it.

For local iPhone testing, use the mobile-safe dev command instead:

```bash
npm run dev:mobile
```

- `npm run dev:mobile` binds both servers to `0.0.0.0` so your iPhone can reach them over Tailscale or your local network.
- Browser-facing API calls are routed through the Next.js proxy at `/api/backend/*`, so the phone does not need a separate FastAPI URL.
- The command prints the checkout-local web and API ports when it starts. Use the web port for the iPhone app URL.

If you want to run the processes separately:

```bash
npm run dev:web
npm run api:dev
```

Useful `HELA_*` overrides:

```bash
HELA_PROJECT_ROOT=/path/to/helaicopter
HELA_CLAUDE_DIR=/path/to/.claude
HELA_CODEX_DIR=/path/to/.codex
HELA_OPENCLAW_DIR=/path/to/.openclaw
```

Helpful checks:

```bash
curl http://127.0.0.1:30000/health
curl http://127.0.0.1:30000/gateway/direction
open http://127.0.0.1:30000/openapi.json
npm run api:openapi
```

## External Agent MCP Surface

The FastAPI backend now mounts a curated FastMCP endpoint for external agents at:

```text
http://127.0.0.1:30000/mcp
```

The MCP surface is intentionally analysis-oriented:

- read access to analytics, conversations, DAGs, history, plans, projects, tasks, orchestration facts, and evaluation prompt listings
- conversation evaluation creation so agents can run eval workflows
- no auth credential management, worker control, database refresh, or orchestration mutation endpoints

## Run On Your iPhone

Short version:

```bash
# 1. Start phone-reachable dev servers
npm run dev:mobile

# 2. Point Capacitor at your Mac over Tailscale
export HELA_MOBILE_SERVER_URL=http://YOUR-MAC-NAME:WEB_PORT

# 3. Sync native iOS config and open Xcode
npm run mobile:ios:sync
npm run mobile:ios:open
```

Then in Xcode:

1. Connect your iPhone by cable
2. Select the `App` target
3. Open `Signing & Capabilities`
4. Choose your Apple ID personal team
5. Pick your iPhone as the run destination
6. Press the Run button

Detailed walkthrough:

- [iPhone developer mode guide](./docs/guides/iphone-dev-mode.md)

## OpenAPI Artifacts

Generated OpenAPI snapshots live under `public/openapi/`:

- `public/openapi/helaicopter-api.json`
- `public/openapi/helaicopter-api.yaml`
- `public/openapi/helaicopter-frontend-app-api.json`

Regenerate them whenever the backend contract changes:

```bash
npm run api:openapi
```

## Features

### Analytics

The homepage shows stats cards, cost breakdowns, daily usage charts, tool usage, model breakdowns, and conversations per day, all scoped to a selectable date range and provider filter.

### Conversations

- Filterable list with search, project filter, date range, and provider filter
- Conversation viewer with messages, context, sub-agents, tasks, and raw JSON tabs
- Cost and token breakdowns per conversation

### Conversation DAGs

Visual graph view of conversation relationships and sub-agent trees.

### Plans

Browse and view saved implementation plans from `~/.claude/plans/`.

### Databases

Inspect local database artifacts such as SQLite and DuckDB through the Databases page.

### Evaluation Prompts

Browse and manage evaluation prompt templates.

### Pricing Reference

Dedicated page documenting the pricing data used for cost estimates across supported providers.

## Runtime Architecture

- **FastAPI** is the single network gateway for the product.
- **SQLite** stores app-local metadata, refresh bookkeeping, evaluations, and historical detail tables.
- **DuckDB** remains an optional analytics and inspection artifact exposed through the Databases page and API.

## Frontend/Backend Split

- `src/` contains the frontend routes, components, hooks, and TypeScript client code.
- `python/helaicopter_api/` owns the FastAPI app, routers, dependency wiring, and application services.
- Compatibility shim: `src/lib/client/normalize.ts` still accepts both legacy camelCase payloads and current snake_case FastAPI responses during the remaining migration cleanup.
- Backend rollout details and verification commands live in `docs/fastapi-backend-rollout.md`.

Frontend runtime validation lives under `src/lib/client/schemas/`. The intended pattern is:

1. Parse backend JSON, route/query state, or form payloads with Zod.
2. Normalize validated payloads into UI-facing types in `src/lib/client/normalize.ts`.
3. Treat FastAPI and Pydantic as the backend contract authority.

## Project Structure

```text
python/
└── helaicopter_api/               # FastAPI backend and application services
src/
├── app/                           # Frontend routes and layouts
│   ├── layout.tsx                 # Root layout with sidebar
│   ├── page.tsx                   # Analytics homepage
│   ├── conversations/
│   ├── dags/page.tsx              # Conversation DAG viewer
│   ├── databases/page.tsx         # Database inspector
│   ├── plans/
│   ├── pricing/page.tsx           # Pricing reference
│   ├── prompts/page.tsx           # Evaluation prompts
│   └── schema/page.tsx            # API schema browser
├── components/                    # React UI building blocks
├── hooks/                         # SWR data hooks
└── lib/
    ├── client/                    # Endpoint builders, fetchers, mutations
    ├── constants.ts               # Shared pricing tables
    ├── evaluation-models.ts       # Frontend evaluation form options
    ├── path-encoding.ts           # Project path display helpers
    ├── pricing.ts                 # Cost calculation utilities
    ├── types.ts                   # Frontend data contracts
    └── utils.ts                   # UI helper utilities
```

## Tech Stack

- [Next.js 16](https://nextjs.org/)
- [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS v4](https://tailwindcss.com/)
- [Radix UI](https://www.radix-ui.com/)
- [SWR](https://swr.vercel.app/)
- [Recharts](https://recharts.org/)
- [react-markdown](https://github.com/remarkjs/react-markdown)
- [date-fns](https://date-fns.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)

## Scripts

```bash
npm run dev              # Start Next.js + FastAPI together
npm run dev:web          # Start only the Next.js development server
npm run api:dev          # Start only the FastAPI backend with uvicorn
npm run api:openapi      # Regenerate OpenAPI artifacts
npm run build            # Production frontend build
npm run start            # Start the production Next.js server
npm run lint             # ESLint
npm run db:refresh       # Run the Python refresh pipeline
npm run db:migrate:oltp  # Apply OLTP alembic migrations
npm run db:migrate:olap  # Apply OLAP alembic migrations
npm run db:export        # Export parsed data from repo tooling
```

## Validation

```bash
npm run lint
uv run --group dev pytest -q
```

## Troubleshooting

- If the frontend cannot reach the backend, confirm `npm run dev` or `npm run api:dev` is running and `NEXT_PUBLIC_API_BASE_URL` points to the correct origin.
- If the backend cannot find local conversation data, set `HELA_CLAUDE_DIR`, `HELA_CODEX_DIR`, `HELA_OPENCLAW_DIR`, or `HELA_PROJECT_ROOT` explicitly.
- If API behavior looks wrong, compare `http://127.0.0.1:30000/openapi.json` against the routers under `python/helaicopter_api/router/`.

## License

Internal use only.
