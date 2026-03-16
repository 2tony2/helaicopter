# Helaicopter

A local Next.js app for browsing your [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://developers.openai.com/codex/) conversations, plans, and token/cost analytics. Reads directly from `~/.claude/` and `~/.codex/` — no data leaves your machine.

## Quick Start

```bash
# Clone and install
git clone https://github.com/curative/helaicopter.git
cd helaicopter
npm install

# Run
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Requirements

- **Node.js** 20+ (22+ recommended)
- **npm** 10+
- **Claude Code** and/or **Codex** installed (the app reads from `~/.claude/` and `~/.codex/`)

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
src/
├── app/
│   ├── layout.tsx                  # Root layout with sidebar
│   ├── page.tsx                    # Analytics homepage
│   ├── conversations/
│   │   ├── page.tsx                # Conversation list
│   │   └── [projectPath]/[sessionId]/page.tsx
│   ├── plans/
│   │   ├── page.tsx                # Plans list
│   │   └── [slug]/page.tsx         # Plan viewer
│   ├── pricing/page.tsx            # Pricing reference
│   └── api/                        # Server-side API routes
│       ├── conversations/          # List + detail
│       ├── subagents/              # Sub-agent conversation
│       ├── plans/                  # Plans list + detail
│       ├── analytics/              # Aggregated analytics
│       ├── projects/               # Project list
│       ├── history/                # Command history
│       └── tasks/                  # Session tasks
├── lib/
│   ├── types.ts                    # All TypeScript types
│   ├── constants.ts                # Paths, Claude + OpenAI pricing tables
│   ├── pricing.ts                  # Cost calculation utilities
│   ├── jsonl-parser.ts             # Streaming Claude JSONL parser
│   ├── codex-types.ts              # Codex JSONL event types
│   ├── codex-jsonl-parser.ts       # Streaming Codex JSONL parser
│   ├── codex-conversation-processor.ts  # Codex events → display model
│   ├── codex-data.ts               # Codex data access (sessions + SQLite)
│   ├── claude-data.ts              # Unified data access layer (Claude + Codex)
│   ├── conversation-processor.ts   # Claude events → display model + context analytics
│   ├── path-encoding.ts            # Project path encoding
│   ├── cache.ts                    # In-memory LRU cache
│   └── utils.ts                    # cn(), model badge helpers
├── hooks/
│   ├── use-conversations.ts        # SWR hooks
│   └── use-plans.ts
└── components/
    ├── ui/                         # shadcn-style primitives + provider filter
    ├── layout/app-sidebar.tsx      # Sidebar navigation
    ├── conversation/
    │   ├── conversation-list.tsx    # With provider filter + model badges
    │   ├── conversation-viewer.tsx  # Tabs: messages, context, subagents, tasks, raw
    │   ├── message-card.tsx
    │   ├── thinking-block.tsx
    │   ├── tool-call-block.tsx
    │   ├── token-usage-badge.tsx    # 4-badge split with cost
    │   └── context-tab.tsx          # Per-tool/step context analytics
    ├── plans/plan-viewer.tsx
    └── analytics/
        ├── stats-card.tsx
        └── charts.tsx
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
npm run dev      # Start development server (port 3000)
npm run build    # Production build
npm run start    # Start production server
npm run lint     # ESLint
npm run db:bootstrap:clickhouse        # Apply the tracked ClickHouse schema to a running server
npm run db:bootstrap:clickhouse:local  # Start/reuse a local ClickHouse container and initialize the schema
```

## ClickHouse Bootstrap

The kappa migration bootstrap assets live under `sql/clickhouse/` and can be applied to a local ClickHouse instance with:

```bash
npm run db:bootstrap:clickhouse:local
```

If you already have ClickHouse running, use:

```bash
npm run db:bootstrap:clickhouse
```

`npm run db:bootstrap:clickhouse:local` starts or reuses a local `clickhouse/clickhouse-server:25.3` container, connects on `127.0.0.1:8123`, defaults the local user/password to `helaicopter` / `helaicopter`, and creates the `helaicopter` database. Override connection settings with:

```bash
HELAICOPTER_CLICKHOUSE_HOST=127.0.0.1
HELAICOPTER_CLICKHOUSE_PORT=8123
HELAICOPTER_CLICKHOUSE_NATIVE_PORT=9000
HELAICOPTER_CLICKHOUSE_DATABASE=helaicopter
HELAICOPTER_CLICKHOUSE_USER=helaicopter
HELAICOPTER_CLICKHOUSE_PASSWORD=helaicopter
HELAICOPTER_CLICKHOUSE_SECURE=0
```

The detailed schema layout, partitions, and sort keys are documented in [`docs/clickhouse-schema.md`](docs/clickhouse-schema.md).

## License

Internal use only.
