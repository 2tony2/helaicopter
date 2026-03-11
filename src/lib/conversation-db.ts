import Database from "better-sqlite3";
import { existsSync } from "fs";
import { join } from "path";
import type {
  ContextAnalytics,
  ConversationPlan,
  ConversationSummary,
  DisplayBlock,
  ProcessedConversation,
  TokenUsage,
} from "@/lib/types";
import { daysAgoIso, startOfTodayIso } from "@/lib/time-windows";

const OLTP_DB_PATH = join(
  process.cwd(),
  "public",
  "database-artifacts",
  "oltp",
  "helaicopter_oltp.sqlite"
);

type ConversationRow = {
  conversation_id: string;
  provider: string;
  session_id: string;
  project_path: string;
  project_name: string;
  first_message: string;
  started_at: string;
  ended_at: string;
  message_count: number;
  model: string | null;
  git_branch: string | null;
  reasoning_effort: string | null;
  speed: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_write_tokens: number;
  total_cache_read_tokens: number;
  total_reasoning_tokens: number;
  tool_use_count: number;
  subagent_count: number;
  task_count: number;
};

type ConversationMessageRow = {
  message_id: string;
  ordinal: number;
  role: "user" | "assistant";
  timestamp: string;
  model: string | null;
  reasoning_tokens: number;
  speed: string | null;
  input_tokens: number;
  output_tokens: number;
  cache_write_tokens: number;
  cache_read_tokens: number;
};

type MessageBlockRow = {
  message_id: string;
  block_index: number;
  block_type: string;
  text_content: string | null;
  tool_use_id: string | null;
  tool_name: string | null;
  tool_input_json: string | null;
  tool_result_text: string | null;
  is_error: number;
};

type PlanRow = {
  plan_id: string;
  slug: string;
  title: string;
  preview: string;
  content: string;
  provider: "claude" | "codex";
  timestamp: string;
  model: string | null;
  explanation: string | null;
  steps_json: string | null;
};

type SubagentRow = {
  agent_id: string;
  description: string | null;
  subagent_type: string | null;
  nickname: string | null;
  has_file: number;
};

type ContextBucketRow = {
  label: string;
  category: "tool" | "mcp" | "subagent" | "thinking" | "conversation";
  input_tokens: number;
  output_tokens: number;
  cache_write_tokens: number;
  cache_read_tokens: number;
  total_tokens: number;
  calls: number;
};

type ContextStepRow = {
  message_id: string;
  ordinal: number;
  role: "user" | "assistant";
  label: string;
  category: "tool" | "mcp" | "subagent" | "thinking" | "conversation";
  timestamp: string;
  input_tokens: number;
  output_tokens: number;
  cache_write_tokens: number;
  cache_read_tokens: number;
  total_tokens: number;
};

function openReadonlyDb(): Database.Database | null {
  if (!existsSync(OLTP_DB_PATH)) {
    return null;
  }

  try {
    const db = new Database(OLTP_DB_PATH, { readonly: true });
    db.pragma("busy_timeout = 5000");
    return db;
  } catch {
    return null;
  }
}

function parseTimestamp(value: string | null | undefined): number {
  return value ? new Date(value).getTime() : 0;
}

function providerForProjectPath(projectPath: string): "claude" | "codex" {
  return projectPath.startsWith("codex:") ? "codex" : "claude";
}

function conversationIdFor(projectPath: string, sessionId: string): string {
  return `${providerForProjectPath(projectPath)}:${sessionId}`;
}

function placeholders(values: readonly string[]): string {
  return values.map(() => "?").join(", ");
}

function parseJson<T>(value: string | null | undefined, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function queryHistoricalConversationRows(
  db: Database.Database,
  projectFilter?: string,
  days?: number
): ConversationRow[] {
  const clauses = ["datetime(started_at) < datetime(?)"];
  const params: unknown[] = [startOfTodayIso()];

  if (projectFilter) {
    clauses.push("project_path = ?");
    params.push(projectFilter);
  }

  if (days) {
    clauses.push("datetime(started_at) >= datetime(?)");
    params.push(daysAgoIso(days));
  }

  return db
    .prepare(
      `
        SELECT
          conversation_id,
          provider,
          session_id,
          project_path,
          project_name,
          first_message,
          started_at,
          ended_at,
          message_count,
          model,
          git_branch,
          reasoning_effort,
          speed,
          total_input_tokens,
          total_output_tokens,
          total_cache_write_tokens,
          total_cache_read_tokens,
          total_reasoning_tokens,
          tool_use_count,
          subagent_count,
          task_count
        FROM conversations
        WHERE ${clauses.join(" AND ")}
        ORDER BY datetime(started_at) DESC
      `
    )
    .all(...params) as ConversationRow[];
}

function mapUsage(row: {
  input_tokens: number;
  output_tokens: number;
  cache_write_tokens: number;
  cache_read_tokens: number;
}): TokenUsage {
  return {
    input_tokens: row.input_tokens || 0,
    output_tokens: row.output_tokens || 0,
    cache_creation_input_tokens: row.cache_write_tokens || 0,
    cache_read_input_tokens: row.cache_read_tokens || 0,
  };
}

export function listHistoricalConversationSummaries(
  projectFilter?: string,
  days?: number
): ConversationSummary[] {
  const db = openReadonlyDb();
  if (!db) {
    return [];
  }

  try {
    const rows = queryHistoricalConversationRows(db, projectFilter, days);
    const conversationIds = rows.map((row) => row.conversation_id);

    const toolBreakdowns = new Map<string, Record<string, number>>();
    const subagentBreakdowns = new Map<string, Record<string, number>>();

    if (conversationIds.length > 0) {
      const toolRows = db
        .prepare(
          `
            SELECT cm.conversation_id, mb.tool_name, COUNT(*) AS count
            FROM conversation_messages cm
            JOIN message_blocks mb ON mb.message_id = cm.message_id
            WHERE cm.conversation_id IN (${placeholders(conversationIds)})
              AND mb.block_type = 'tool_call'
              AND mb.tool_name IS NOT NULL
            GROUP BY cm.conversation_id, mb.tool_name
          `
        )
        .all(...conversationIds) as Array<{
          conversation_id: string;
          tool_name: string;
          count: number;
        }>;

      for (const row of toolRows) {
        const breakdown = toolBreakdowns.get(row.conversation_id) ?? {};
        breakdown[row.tool_name] = row.count;
        toolBreakdowns.set(row.conversation_id, breakdown);
      }

      const subagentRows = db
        .prepare(
          `
            SELECT conversation_id, COALESCE(subagent_type, 'unknown') AS subagent_type, COUNT(*) AS count
            FROM conversation_subagents
            WHERE conversation_id IN (${placeholders(conversationIds)})
            GROUP BY conversation_id, COALESCE(subagent_type, 'unknown')
          `
        )
        .all(...conversationIds) as Array<{
          conversation_id: string;
          subagent_type: string;
          count: number;
        }>;

      for (const row of subagentRows) {
        const breakdown = subagentBreakdowns.get(row.conversation_id) ?? {};
        breakdown[row.subagent_type] = row.count;
        subagentBreakdowns.set(row.conversation_id, breakdown);
      }
    }

    return rows.map((row) => ({
      sessionId: row.session_id,
      projectPath: row.project_path,
      projectName: row.project_name,
      firstMessage: row.first_message,
      timestamp: parseTimestamp(row.started_at),
      messageCount: row.message_count,
      model: row.model ?? undefined,
      totalInputTokens: row.total_input_tokens,
      totalOutputTokens: row.total_output_tokens,
      totalCacheCreationTokens: row.total_cache_write_tokens,
      totalCacheReadTokens: row.total_cache_read_tokens,
      toolUseCount: row.tool_use_count,
      toolBreakdown: toolBreakdowns.get(row.conversation_id) ?? {},
      subagentCount: row.subagent_count,
      subagentTypeBreakdown:
        subagentBreakdowns.get(row.conversation_id) ?? {},
      taskCount: row.task_count,
      gitBranch: row.git_branch ?? undefined,
      reasoningEffort: row.reasoning_effort ?? undefined,
      speed: row.speed ?? undefined,
      totalReasoningTokens: row.total_reasoning_tokens || 0,
    }));
  } finally {
    db.close();
  }
}

export function getHistoricalConversation(
  projectPath: string,
  sessionId: string
): ProcessedConversation | null {
  const db = openReadonlyDb();
  if (!db) {
    return null;
  }

  try {
    const conversationRow = db
      .prepare(
        `
          SELECT
            conversation_id,
            provider,
            session_id,
            project_path,
            project_name,
            first_message,
            started_at,
            ended_at,
            message_count,
            model,
            git_branch,
            reasoning_effort,
            speed,
            total_input_tokens,
            total_output_tokens,
            total_cache_write_tokens,
            total_cache_read_tokens,
            total_reasoning_tokens,
            tool_use_count,
            subagent_count,
            task_count
          FROM conversations
          WHERE project_path = ?
            AND session_id = ?
            AND datetime(started_at) < datetime(?)
          LIMIT 1
        `
      )
      .get(projectPath, sessionId, startOfTodayIso()) as
      | ConversationRow
      | undefined;

    if (!conversationRow) {
      return null;
    }

    const messageRows = db
      .prepare(
        `
          SELECT
            message_id,
            ordinal,
            role,
            timestamp,
            model,
            reasoning_tokens,
            speed,
            input_tokens,
            output_tokens,
            cache_write_tokens,
            cache_read_tokens
          FROM conversation_messages
          WHERE conversation_id = ?
          ORDER BY ordinal ASC
        `
      )
      .all(conversationRow.conversation_id) as ConversationMessageRow[];

    const messageIds = messageRows.map((row) => row.message_id);
    const blockRows =
      messageIds.length > 0
        ? (db
            .prepare(
              `
                SELECT
                  message_id,
                  block_index,
                  block_type,
                  text_content,
                  tool_use_id,
                  tool_name,
                  tool_input_json,
                  tool_result_text,
                  is_error
                FROM message_blocks
                WHERE message_id IN (${placeholders(messageIds)})
                ORDER BY message_id ASC, block_index ASC
              `
            )
            .all(...messageIds) as MessageBlockRow[])
        : [];

    const blocksByMessageId = new Map<string, DisplayBlock[]>();
    for (const block of blockRows) {
      const entries = blocksByMessageId.get(block.message_id) ?? [];
      if (block.block_type === "thinking") {
        const thinking = block.text_content ?? "";
        entries.push({
          type: "thinking",
          thinking,
          charCount: thinking.length,
        });
      } else if (block.block_type === "tool_call") {
        entries.push({
          type: "tool_call",
          toolUseId: block.tool_use_id ?? `${block.message_id}:${block.block_index}`,
          toolName: block.tool_name ?? "unknown",
          input: parseJson<Record<string, unknown>>(block.tool_input_json, {}),
          result: block.tool_result_text ?? undefined,
          isError: Boolean(block.is_error),
        });
      } else {
        entries.push({
          type: "text",
          text: block.text_content ?? "",
        });
      }
      blocksByMessageId.set(block.message_id, entries);
    }

    const messages = messageRows.map((row) => {
      const usage = mapUsage(row);
      const hasUsage =
        usage.input_tokens > 0 ||
        usage.output_tokens > 0 ||
        (usage.cache_creation_input_tokens ?? 0) > 0 ||
        (usage.cache_read_input_tokens ?? 0) > 0;

      return {
        id: row.message_id,
        role: row.role,
        timestamp: parseTimestamp(row.timestamp),
        blocks: blocksByMessageId.get(row.message_id) ?? [],
        usage: hasUsage ? usage : undefined,
        model: row.model ?? undefined,
        reasoningTokens: row.reasoning_tokens || undefined,
        speed: row.speed ?? undefined,
      };
    });

    const planRows = db
      .prepare(
        `
          SELECT plan_id, slug, title, preview, content, provider, timestamp, model, explanation, steps_json
          FROM conversation_plans
          WHERE conversation_id = ?
          ORDER BY datetime(timestamp) ASC
        `
      )
      .all(conversationRow.conversation_id) as PlanRow[];

    const plans: ConversationPlan[] = planRows.map((row) => ({
      id: row.plan_id,
      slug: row.slug,
      title: row.title,
      preview: row.preview,
      content: row.content,
      provider: row.provider,
      timestamp: parseTimestamp(row.timestamp),
      sessionId,
      projectPath,
      model: row.model ?? undefined,
      explanation: row.explanation ?? undefined,
      steps: parseJson(row.steps_json, undefined),
    }));

    const subagents = (
      db
        .prepare(
          `
            SELECT agent_id, description, subagent_type, nickname, has_file
            FROM conversation_subagents
            WHERE conversation_id = ?
            ORDER BY agent_id ASC
          `
        )
        .all(conversationRow.conversation_id) as SubagentRow[]
    ).map((row) => ({
      agentId: row.agent_id,
      description: row.description ?? undefined,
      subagentType: row.subagent_type ?? undefined,
      nickname: row.nickname ?? undefined,
      hasFile: Boolean(row.has_file),
      projectPath,
      sessionId,
    }));

    const contextBuckets = (
      db
        .prepare(
          `
            SELECT
              label,
              category,
              input_tokens,
              output_tokens,
              cache_write_tokens,
              cache_read_tokens,
              total_tokens,
              calls
            FROM context_buckets
            WHERE conversation_id = ?
            ORDER BY bucket_row_id ASC
          `
        )
        .all(conversationRow.conversation_id) as ContextBucketRow[]
    ).map((row) => ({
      label: row.label,
      category: row.category,
      inputTokens: row.input_tokens,
      outputTokens: row.output_tokens,
      cacheWriteTokens: row.cache_write_tokens,
      cacheReadTokens: row.cache_read_tokens,
      totalTokens: row.total_tokens,
      calls: row.calls,
    }));

    const contextSteps = (
      db
        .prepare(
          `
            SELECT
              message_id,
              ordinal,
              role,
              label,
              category,
              timestamp,
              input_tokens,
              output_tokens,
              cache_write_tokens,
              cache_read_tokens,
              total_tokens
            FROM context_steps
            WHERE conversation_id = ?
            ORDER BY ordinal ASC
          `
        )
        .all(conversationRow.conversation_id) as ContextStepRow[]
    ).map((row) => ({
      messageId: row.message_id,
      index: row.ordinal,
      role: row.role,
      label: row.label,
      category: row.category,
      timestamp: parseTimestamp(row.timestamp),
      inputTokens: row.input_tokens,
      outputTokens: row.output_tokens,
      cacheWriteTokens: row.cache_write_tokens,
      cacheReadTokens: row.cache_read_tokens,
      totalTokens: row.total_tokens,
    }));

    const contextAnalytics: ContextAnalytics = {
      buckets: contextBuckets,
      steps: contextSteps,
    };

    const apiCalls = messages.filter((message) => message.usage).length;
    const peakContextWindow = messages.reduce((peak, message) => {
      const usage = message.usage;
      if (!usage) return peak;
      return Math.max(
        peak,
        (usage.input_tokens || 0) +
          (usage.cache_creation_input_tokens || 0) +
          (usage.cache_read_input_tokens || 0)
      );
    }, 0);

    return {
      sessionId,
      projectPath,
      messages,
      plans,
      totalUsage: {
        input_tokens: conversationRow.total_input_tokens,
        output_tokens: conversationRow.total_output_tokens,
        cache_creation_input_tokens: conversationRow.total_cache_write_tokens,
        cache_read_input_tokens: conversationRow.total_cache_read_tokens,
      },
      model: conversationRow.model ?? undefined,
      gitBranch: conversationRow.git_branch ?? undefined,
      startTime: parseTimestamp(conversationRow.started_at),
      endTime: parseTimestamp(conversationRow.ended_at),
      subagents,
      contextAnalytics,
      contextWindow: {
        peakContextWindow,
        apiCalls,
        cumulativeTokens:
          conversationRow.total_input_tokens +
          conversationRow.total_output_tokens +
          conversationRow.total_cache_write_tokens +
          conversationRow.total_cache_read_tokens,
      },
      reasoningEffort: conversationRow.reasoning_effort ?? undefined,
      speed: conversationRow.speed ?? undefined,
      totalReasoningTokens: conversationRow.total_reasoning_tokens || 0,
    };
  } finally {
    db.close();
  }
}

export function getHistoricalTasksForSession(sessionId: string): unknown[] | null {
  const db = openReadonlyDb();
  if (!db) {
    return null;
  }

  try {
    const conversation = db
      .prepare(
        `
          SELECT conversation_id
          FROM conversations
          WHERE session_id = ?
            AND datetime(started_at) < datetime(?)
          LIMIT 1
        `
      )
      .get(sessionId, startOfTodayIso()) as { conversation_id: string } | undefined;

    if (!conversation) {
      return null;
    }

    const rows = db
      .prepare(
        `
          SELECT task_json
          FROM conversation_tasks
          WHERE conversation_id = ?
          ORDER BY ordinal ASC
        `
      )
      .all(conversation.conversation_id) as Array<{ task_json: string }>;

    return rows.map((row) => parseJson(row.task_json, null)).filter((row) => row !== null);
  } finally {
    db.close();
  }
}

export function hasHistoricalConversation(projectPath: string, sessionId: string): boolean {
  const db = openReadonlyDb();
  if (!db) {
    return false;
  }

  try {
    const conversationId = conversationIdFor(projectPath, sessionId);
    const row = db
      .prepare(
        `
          SELECT 1
          FROM conversations
          WHERE conversation_id = ?
            AND datetime(started_at) < datetime(?)
          LIMIT 1
        `
      )
      .get(conversationId, startOfTodayIso());

    return Boolean(row);
  } finally {
    db.close();
  }
}
