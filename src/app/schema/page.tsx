import type { Metadata } from "next";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  CODEX_DB_PATH,
  CODEX_HISTORY_FILE,
  CODEX_SESSIONS_DIR,
  HISTORY_FILE,
  PROJECTS_DIR,
  TASKS_DIR,
} from "@/lib/constants";

export const metadata: Metadata = {
  title: "Schema | Helaicopter",
  description:
    "Where Claude and Codex data comes from, how the current parsing framework works, and which normalized models Helaicopter serves to the UI.",
};

const claudeSources = [
  {
    label: "Conversation JSONL",
    path: `${PROJECTS_DIR}/<encoded-project>/<session-id>.jsonl`,
    detail:
      "Primary Claude Code source. Each line is a raw event with nested message content, tool blocks, assistant-side token usage, and optional `planContent` snapshots on plan-bearing events.",
  },
  {
    label: "Subagent JSONL",
    path: `${PROJECTS_DIR}/<encoded-project>/<session-id>/subagents/agent-<id>.jsonl`,
    detail:
      "Claude subagent transcripts. Parent sessions reference them through Task tool usage and tool result metadata.",
  },
  {
    label: "Tasks",
    path: `${TASKS_DIR}/<session-id>/`,
    detail:
      "Per-session task files used by the task tab and session-level task counts.",
  },
  {
    label: "History",
    path: HISTORY_FILE,
    detail:
      "Flattened Claude history entries used for the global history endpoint.",
  },
];

const codexSources = [
  {
    label: "Session JSONL",
    path: `${CODEX_SESSIONS_DIR}/YYYY/MM/DD/rollout-<timestamp>-<session-id>.jsonl`,
    detail:
      "Primary Codex source. Messages, reasoning, tool calls, search calls, token counters, and `update_plan` function calls arrive as separate line items.",
  },
  {
    label: "SQLite thread metadata",
    path: CODEX_DB_PATH,
    detail:
      "Thread enrichment for cwd, git branch, first user message, child-thread lineage, agent role, and nickname fields that are not reliable in JSONL alone.",
  },
  {
    label: "History",
    path: CODEX_HISTORY_FILE,
    detail:
      "Session-level history entries used in the unified history feed.",
  },
];

const frameworkRows = [
  {
    title: "Discovery",
    detail:
      "Claude sessions are scanned from project folders. Codex sessions are found recursively under dated session directories, with a fast mtime cutoff before parsing.",
  },
  {
    title: "Summary extractors",
    detail:
      "List views use streaming JSONL readers. Claude summaries read assistant usage and Task tool blocks. Plan discovery scans Claude `planContent` events and Codex `update_plan` calls. Codex summaries read session_meta, response_item, turn_context, and the final cumulative token_count event.",
  },
  {
    title: "Enrichment",
    detail:
      "Claude adds task counts and subagent files from disk. Codex merges SQLite thread metadata, then rolls child threads back into the parent summary using parent_thread_id.",
  },
  {
    title: "Detail processors",
    detail:
      "Full transcript views parse the entire file and normalize provider-specific events into a shared ProcessedConversation with display blocks, token usage, context analytics, and subagent metadata.",
  },
  {
    title: "Cache invalidation",
    detail:
      "Summary and detail results are cached in memory by file path and file mtime, so edits on disk invalidate stale entries automatically.",
  },
];

const usageRows = [
  {
    area: "Conversation list",
    detail:
      "Uses summary extraction for first message, timestamps, model, tool counts, token totals, branch, subagent rollups, and provider-aware project naming.",
  },
  {
    area: "Conversation viewer",
    detail:
      "Uses normalized ProcessedConversation messages so Claude and Codex render through the same UI for text, thinking, tool calls, tool results, token badges, and per-conversation plans.",
  },
  {
    area: "Plans library",
    detail:
      "The global plans tab merges legacy markdown files, Claude `planContent` snapshots, and Codex `update_plan` snapshots into one provider-aware list with links back to the source conversation.",
  },
  {
    area: "Context analytics",
    detail:
      "Builds per-tool and per-step token attribution buckets from normalized assistant steps. Claude uses message usage directly; Codex derives step deltas from cumulative token_count events.",
  },
  {
    area: "Cost estimation",
    detail:
      "Maps normalized token usage onto Claude and OpenAI pricing tables, with Claude cache writes and reads handled separately from Codex cached input reads and reasoning tokens.",
  },
];

function CodeBlock({
  children,
}: Readonly<{
  children: string;
}>) {
  return (
    <pre className="overflow-x-auto rounded-xl border bg-muted/40 p-4 text-xs leading-6">
      <code>{children}</code>
    </pre>
  );
}

export default function SchemaPage() {
  return (
    <div className="max-w-6xl space-y-8">
      <div className="space-y-3">
        <Badge variant="secondary" className="text-sm">
          Internal data reference
        </Badge>
        <div>
          <h1 className="text-2xl font-bold">Schema</h1>
          <p className="mt-2 max-w-3xl text-muted-foreground">
            This page documents the current parsing framework: where Claude and
            Codex data comes from, how summaries and full conversations are
            built, where extra metadata is joined in, and which normalized
            models are served to the UI.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Claude sources</CardTitle>
            <CardDescription>
              Everything is read locally from the Claude Code workspace.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {claudeSources.map((source) => (
              <div key={source.label} className="rounded-lg border p-4">
                <div className="font-medium">{source.label}</div>
                <div className="mt-1 font-mono text-xs text-muted-foreground">
                  {source.path}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {source.detail}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Codex sources</CardTitle>
            <CardDescription>
              Codex data is combined from JSONL sessions and SQLite metadata.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {codexSources.map((source) => (
              <div key={source.label} className="rounded-lg border p-4">
                <div className="font-medium">{source.label}</div>
                <div className="mt-1 font-mono text-xs text-muted-foreground">
                  {source.path}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {source.detail}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Current parsing framework</CardTitle>
          <CardDescription>
            Helaicopter now treats parsing as a staged pipeline, not a single
            raw-schema reader.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {frameworkRows.map((row) => (
            <div key={row.title} className="rounded-xl border p-4">
              <div className="font-medium">{row.title}</div>
              <p className="mt-2 text-sm text-muted-foreground">
                {row.detail}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Claude raw schema</CardTitle>
            <CardDescription>
              Claude keeps most parsing state inside a single event stream with
              nested message content blocks and task metadata on adjacent user
              events. Plans, when present, are stored as `planContent` on raw
              events in the same JSONL.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <CodeBlock>{`type RawEvent = {
  type: "user" | "assistant" | "progress" | "file-history-snapshot";
  uuid: string;
  parentUuid?: string;
  timestamp: number | string;
  cwd?: string;
  gitBranch?: string;
  agentId?: string;
  planContent?: string;
  toolUseResult?: {
    agentId?: string;
    description?: string;
    status?: string;
  };
  message?: {
    role: "user" | "assistant";
    model?: string;
    content: Array<
      | { type: "text"; text: string }
      | { type: "thinking"; thinking: string }
      | { type: "tool_use"; id: string; name: string; input: Record<string, unknown> }
      | { type: "tool_result"; tool_use_id: string; content: string | RawContentBlock[]; is_error?: boolean }
    > | string;
    usage?: {
      input_tokens: number;
      output_tokens: number;
      cache_creation_input_tokens?: number;
      cache_read_input_tokens?: number;
      service_tier?: string;
      speed?: string;
    };
  };
};`}</CodeBlock>
            <p className="text-sm text-muted-foreground">
              The Claude detail processor skips `progress` and
              `file-history-snapshot`, pairs `tool_result` blocks back onto the
              original `tool_use`, and records `Task` invocations as subagent
              work. Per-step token usage already lives on assistant messages.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Codex raw schema</CardTitle>
            <CardDescription>
              Codex splits session metadata, assistant output, tool activity,
              plan snapshots, and token accounting across separate line types
              that must be joined during parsing.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <CodeBlock>{`type CodexRawLine = {
  timestamp: string;
  type: "session_meta" | "response_item" | "event_msg" | "turn_context";
  payload:
    | {
        id: string;
        cwd: string;
        source:
          | string
          | {
              subagent?: {
                thread_spawn?: {
                  parent_thread_id?: string;
                  depth?: number;
                  agent_nickname?: string;
                  agent_role?: string;
                };
              };
            };
        agent_nickname?: string;
        agent_role?: string;
        model_provider: string;
      }
    | { type: "message"; role: "user" | "assistant" | "developer"; content: Array<{ type: "input_text" | "output_text"; text: string }> }
    | { type: "function_call"; name: string; arguments: string; call_id: string }
    | { type: "function_call_output"; call_id: string; output: string }
    | { type: "custom_tool_call"; name: string; input: string; call_id: string; status: string }
    | { type: "custom_tool_call_output"; call_id: string; output: string }
    | { type: "web_search_call"; status: string; action?: { query?: string; queries?: string[] } }
    | { type: "reasoning"; summary: Array<{ type: string; text: string }> }
    | {
        type: "token_count";
        info: {
          total_token_usage: {
            input_tokens: number;
            cached_input_tokens: number;
            output_tokens: number;
            reasoning_output_tokens: number;
            total_tokens: number;
          };
          last_token_usage: {
            input_tokens: number;
            cached_input_tokens: number;
            output_tokens: number;
            reasoning_output_tokens: number;
            total_tokens: number;
          };
          model_context_window: number;
        } | null;
      }
    | { type: "task_started" | "task_complete" | "agent_message" | "agent_reasoning" | "user_message" }
    | { model?: string; reasoning_effort?: string };
};`}</CodeBlock>
            <p className="text-sm text-muted-foreground">
              The Codex processor buffers assistant text, reasoning, and tool
              calls until the next cumulative `token_count` event arrives. That
              delta becomes one normalized assistant step. Developer messages
              and duplicate `agent_message` and `agent_reasoning` events are
              skipped, while `update_plan` function calls are normalized into
              structured plan snapshots.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Normalized models used by the UI</CardTitle>
          <CardDescription>
            Both providers are converted into the same summary and detail shapes
            before they hit the frontend components.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <CodeBlock>{`type ConversationSummary = {
  sessionId: string;
  projectPath: string;
  projectName: string;
  firstMessage: string;
  timestamp: number;
  messageCount: number;
  model?: string;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheCreationTokens: number;
  totalCacheReadTokens: number;
  toolUseCount: number;
  toolBreakdown: Record<string, number>;
  subagentCount: number;
  subagentTypeBreakdown: Record<string, number>;
  taskCount: number;
  gitBranch?: string;
  reasoningEffort?: string;
  speed?: string;
  totalReasoningTokens?: number;
};

type ProcessedConversation = {
  sessionId: string;
  projectPath: string;
  messages: ProcessedMessage[];
  plans: ConversationPlan[];
  totalUsage: TokenUsage;
  model?: string;
  gitBranch?: string;
  startTime: number;
  endTime: number;
  subagents: SubagentInfo[];
  reasoningEffort?: string;
  speed?: string;
  totalReasoningTokens?: number;
  contextAnalytics: {
    buckets: ContextBucket[];
    steps: ContextStep[];
  };
  contextWindow: {
    peakContextWindow: number;
    apiCalls: number;
    cumulativeTokens: number;
  };
};`}</CodeBlock>
          <p className="text-sm text-muted-foreground">
            This normalization is what lets the conversation list, analytics
            views, plans tab, subagent tabs, and conversation viewer work
            across Claude and Codex with the same rendering components.
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Provider-specific parsing rules</CardTitle>
            <CardDescription>
              These are the important differences the normalizers handle.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            <div className="rounded-lg border p-4">
              <div className="font-medium text-foreground">Claude</div>
              <p className="mt-2">
                User and assistant content can contain nested blocks, so tool
                calls and tool results are paired by `tool_use_id`. Assistant
                usage already contains step-local input, output, cache write,
                and cache read tokens, and context analytics can attribute those
                tokens immediately.
              </p>
            </div>
            <div className="rounded-lg border p-4">
              <div className="font-medium text-foreground">Codex</div>
              <p className="mt-2">
                Messages, reasoning, tool calls, and tool outputs arrive as
                separate `response_item` records, while token accounting arrives
                later through cumulative `event_msg[token_count]` updates.
                SQLite adds git branch, cwd, agent role, nickname, and parent
                thread lineage that JSONL alone does not reliably provide.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">How the parsed data is used</CardTitle>
            <CardDescription>
              The normalized models feed every major view in the app.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {usageRows.map((row) => (
              <div key={row.area} className="rounded-lg border p-4">
                <div className="font-medium">{row.area}</div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {row.detail}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
