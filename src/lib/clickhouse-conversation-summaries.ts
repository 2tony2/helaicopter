import {
  escapeClickHouseString,
  getClickHouseSettings,
  queryClickHouseRows,
} from "@/lib/clickhouse";
import type { ConversationSummary } from "@/lib/types";

interface ClickHouseConversationSummaryRow {
  provider: string;
  conversation_id: string;
  session_id: string;
  project_path: string;
  project_name: string;
  git_branch: string;
  model_name: string;
  first_message: string;
  conversation_time: string;
  message_count: number | string;
  total_input_tokens: number | string;
  total_output_tokens: number | string;
  total_cache_creation_tokens: number | string;
  total_cache_read_tokens: number | string;
  total_reasoning_tokens: number | string;
  tool_use_count: number | string;
  subagent_count: number | string;
  thread_type: string;
  task_count: number | string;
  reasoning_effort: string;
  speed: string;
}

interface ClickHouseConversationToolRow {
  provider: string;
  conversation_id: string;
  tool_name: string;
  tool_calls: number | string;
  failed_tool_calls: number | string;
}

interface ClickHouseConversationSubagentRow {
  provider: string;
  conversation_id: string;
  subagent_type: string;
  subagent_count: number | string;
}

const DAY_MS = 24 * 60 * 60 * 1000;
const CONVERSATION_STATE_PROVIDER_COLUMN = "`conversation_keys.provider`";
const CONVERSATION_STATE_CONVERSATION_ID_COLUMN =
  "`conversation_keys.conversation_id`";

function toNumber(value: number | string | null | undefined): number {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }
  if (typeof value === "string" && value.length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function parseClickHouseDateTime(value: string): Date {
  if (value.includes("T")) {
    return new Date(value.endsWith("Z") ? value : `${value}Z`);
  }

  return new Date(`${value.replace(" ", "T")}Z`);
}

function buildConversationTimeExpression(tableAlias?: string): string {
  const prefix = tableAlias ? `${tableAlias}.` : "";
  return `coalesce(${prefix}started_at, ${prefix}first_message_time, ${prefix}last_event_at)`;
}

function buildConversationWhereClauses(
  projectFilter?: string,
  days?: number,
  tableAlias?: string
): string[] {
  const conversationTimeExpression = buildConversationTimeExpression(tableAlias);
  const prefix = tableAlias ? `${tableAlias}.` : "";
  const clauses = [`${conversationTimeExpression} IS NOT NULL`];

  if (projectFilter) {
    clauses.push(`${prefix}project_path = '${escapeClickHouseString(projectFilter)}'`);
  }

  if (days) {
    clauses.push(
      `${conversationTimeExpression} >= parseDateTime64BestEffort('${escapeClickHouseString(
        new Date(Date.now() - days * DAY_MS).toISOString()
      )}')`
    );
  }

  return clauses;
}

function buildFilteredConversationsSubquery(
  projectFilter?: string,
  days?: number
): string {
  const database = getClickHouseSettings().database;
  const whereClauses = buildConversationWhereClauses(projectFilter, days, "cs");
  const conversationTimeExpression = buildConversationTimeExpression("cs");

  return `(
  SELECT
    cs.${CONVERSATION_STATE_PROVIDER_COLUMN} AS conversation_provider,
    cs.${CONVERSATION_STATE_CONVERSATION_ID_COLUMN} AS conversation_key_id,
    cs.session_id AS session_id,
    cs.project_path AS project_path,
    cs.project_name AS project_name,
    cs.git_branch AS git_branch,
    nullIf(cs.latest_model, '') AS model_name,
    nullIf(cs.first_message_text, '') AS first_message,
    ${conversationTimeExpression} AS conversation_time,
    toInt64(ifNull(cs.message_count, 0)) AS message_count,
    toInt64(ifNull(cs.total_input_tokens, 0)) AS total_input_tokens,
    toInt64(ifNull(cs.total_output_tokens, 0)) AS total_output_tokens,
    toInt64(ifNull(cs.total_cache_write_tokens, 0)) AS total_cache_creation_tokens,
    toInt64(ifNull(cs.total_cache_read_tokens, 0)) AS total_cache_read_tokens,
    toInt64(ifNull(cs.total_reasoning_tokens, 0)) AS total_reasoning_tokens,
    toInt64(ifNull(cs.tool_call_count, 0)) AS tool_use_count,
    toInt64(ifNull(cs.subagent_count, 0)) AS subagent_count
  FROM ${database}.conversation_state AS cs
  WHERE ${whereClauses.join("\n    AND ")}
)`;
}

export async function queryClickHouseConversationSummaries(
  projectFilter?: string,
  days?: number
): Promise<ConversationSummary[]> {
  const database = getClickHouseSettings().database;
  const filteredConversationsSubquery = buildFilteredConversationsSubquery(
    projectFilter,
    days
  );

  const summariesSql = `
SELECT
  fc.conversation_provider AS provider,
  fc.conversation_key_id AS conversation_id,
  fc.session_id AS session_id,
  fc.project_path AS project_path,
  fc.project_name AS project_name,
  fc.git_branch AS git_branch,
  ifNull(fc.model_name, '') AS model_name,
  ifNull(fc.first_message, '') AS first_message,
  toString(fc.conversation_time) AS conversation_time,
  fc.message_count AS message_count,
  fc.total_input_tokens AS total_input_tokens,
  fc.total_output_tokens AS total_output_tokens,
  fc.total_cache_creation_tokens AS total_cache_creation_tokens,
  fc.total_cache_read_tokens AS total_cache_read_tokens,
  fc.total_reasoning_tokens AS total_reasoning_tokens,
  fc.tool_use_count AS tool_use_count,
  fc.subagent_count AS subagent_count,
  meta.thread_type AS thread_type,
  meta.task_count AS task_count,
  meta.reasoning_effort AS reasoning_effort,
  meta.speed AS speed
FROM ${filteredConversationsSubquery} AS fc
LEFT JOIN (
  SELECT
    ce.provider AS provider,
    ce.conversation_id AS conversation_id,
    multiIf(
      max(if(JSONExtractString(ce.payload_json, 'summary', 'threadType') = 'subagent', 1, 0)) > 0,
      'subagent',
      max(
        if(
          JSONExtractString(
            ce.payload_json,
            'payload',
            'source',
            'subagent',
            'thread_spawn',
            'parent_thread_id'
          ) != '',
          1,
          0
        )
      ) > 0,
      'subagent',
      'main'
    ) AS thread_type,
    greatest(
      max(toInt64(ifNull(JSONExtractInt(ce.payload_json, 'summary', 'taskCount'), 0))),
      max(toInt64(ifNull(JSONExtractInt(ce.payload_json, 'taskCount'), 0)))
    ) AS task_count,
    coalesce(
      argMaxIf(
        nullIf(JSONExtractString(ce.payload_json, 'summary', 'reasoningEffort'), ''),
        ce.event_time,
        JSONExtractString(ce.payload_json, 'summary', 'reasoningEffort') != ''
      ),
      argMaxIf(
        nullIf(JSONExtractString(ce.payload_json, 'payload', 'reasoning_effort'), ''),
        ce.event_time,
        JSONExtractString(ce.payload_json, 'payload', 'reasoning_effort') != ''
      ),
      ''
    ) AS reasoning_effort,
    coalesce(
      argMaxIf(
        nullIf(JSONExtractString(ce.payload_json, 'summary', 'speed'), ''),
        ce.event_time,
        JSONExtractString(ce.payload_json, 'summary', 'speed') != ''
      ),
      argMaxIf(
        nullIf(JSONExtractString(ce.payload_json, 'message', 'usage', 'speed'), ''),
        ce.event_time,
        JSONExtractString(ce.payload_json, 'message', 'usage', 'speed') != ''
      ),
      ''
    ) AS speed
  FROM ${database}.conversation_events AS ce
  INNER JOIN ${filteredConversationsSubquery} AS filtered_meta
    ON ce.provider = filtered_meta.conversation_provider
   AND ce.conversation_id = filtered_meta.conversation_key_id
  GROUP BY ce.provider, ce.conversation_id
) AS meta
  ON fc.conversation_provider = meta.provider
 AND fc.conversation_key_id = meta.conversation_id
ORDER BY
  fc.conversation_time DESC,
  fc.conversation_provider ASC,
  fc.conversation_key_id ASC`;

  const toolRowsSql = `
SELECT
  te.provider AS provider,
  te.conversation_id AS conversation_id,
  te.tool_name AS tool_name,
  count() AS tool_calls,
  countIf(te.error_text != '') AS failed_tool_calls
FROM ${database}.tool_events AS te
INNER JOIN ${filteredConversationsSubquery} AS filtered_tools
  ON te.provider = filtered_tools.conversation_provider
 AND te.conversation_id = filtered_tools.conversation_key_id
GROUP BY te.provider, te.conversation_id, te.tool_name
ORDER BY te.provider ASC, te.conversation_id ASC, te.tool_name ASC`;

  const subagentRowsSql = `
SELECT
  te.provider AS provider,
  te.conversation_id AS conversation_id,
  te.subagent_type AS subagent_type,
  count() AS subagent_count
FROM ${database}.tool_events AS te
INNER JOIN ${filteredConversationsSubquery} AS filtered_subagents
  ON te.provider = filtered_subagents.conversation_provider
 AND te.conversation_id = filtered_subagents.conversation_key_id
WHERE te.subagent_type != ''
GROUP BY te.provider, te.conversation_id, te.subagent_type
ORDER BY te.provider ASC, te.conversation_id ASC, te.subagent_type ASC`;

  const [summaryRows, toolRows, subagentRows] = await Promise.all([
    queryClickHouseRows<ClickHouseConversationSummaryRow>(summariesSql),
    queryClickHouseRows<ClickHouseConversationToolRow>(toolRowsSql),
    queryClickHouseRows<ClickHouseConversationSubagentRow>(subagentRowsSql),
  ]);

  const toolBreakdowns = new Map<string, Record<string, number>>();
  const failedToolCallCounts = new Map<string, number>();
  for (const row of toolRows) {
    const key = `${row.provider}:${row.conversation_id}`;
    const breakdown = toolBreakdowns.get(key) ?? {};
    breakdown[row.tool_name] = toNumber(row.tool_calls);
    toolBreakdowns.set(key, breakdown);
    failedToolCallCounts.set(
      key,
      (failedToolCallCounts.get(key) ?? 0) + toNumber(row.failed_tool_calls)
    );
  }

  const subagentTypeBreakdowns = new Map<string, Record<string, number>>();
  for (const row of subagentRows) {
    const key = `${row.provider}:${row.conversation_id}`;
    const breakdown = subagentTypeBreakdowns.get(key) ?? {};
    breakdown[row.subagent_type] = toNumber(row.subagent_count);
    subagentTypeBreakdowns.set(key, breakdown);
  }

  return summaryRows.map((row) => {
    const key = `${row.provider}:${row.conversation_id}`;
    const threadType = row.thread_type === "subagent" ? "subagent" : "main";

    return {
      sessionId: row.session_id,
      projectPath: row.project_path,
      projectName: row.project_name,
      threadType,
      firstMessage: row.first_message,
      timestamp: parseClickHouseDateTime(row.conversation_time).getTime(),
      messageCount: toNumber(row.message_count),
      model: row.model_name || undefined,
      totalInputTokens: toNumber(row.total_input_tokens),
      totalOutputTokens: toNumber(row.total_output_tokens),
      totalCacheCreationTokens: toNumber(row.total_cache_creation_tokens),
      totalCacheReadTokens: toNumber(row.total_cache_read_tokens),
      toolUseCount: toNumber(row.tool_use_count),
      failedToolCallCount: failedToolCallCounts.get(key) ?? 0,
      toolBreakdown: toolBreakdowns.get(key) ?? {},
      subagentCount: toNumber(row.subagent_count),
      subagentTypeBreakdown: subagentTypeBreakdowns.get(key) ?? {},
      taskCount: toNumber(row.task_count),
      gitBranch: row.git_branch || undefined,
      reasoningEffort: row.reasoning_effort || undefined,
      speed: row.speed || undefined,
      totalReasoningTokens: toNumber(row.total_reasoning_tokens) || undefined,
    };
  });
}
