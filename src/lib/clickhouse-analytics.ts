import {
  buildAnalyticsFromConversations,
  filterAnalyticsConversationsByProvider,
  listRawConversations,
} from "@/lib/claude-data";
import {
  escapeClickHouseString,
  getClickHouseSettings,
  queryClickHouseRows,
} from "@/lib/clickhouse";
import { startOfTodayMs } from "@/lib/time-windows";
import type {
  AnalyticsCostBreakdown,
  AnalyticsCostBreakdownMap,
  AnalyticsData,
  AnalyticsRateValue,
  AnalyticsRates,
  AnalyticsTimeSeries,
  AnalyticsTimeSeriesPoint,
  DailyUsage,
  ProviderBreakdown,
} from "@/lib/types";

type TimeSeriesKey = "hourly" | "daily" | "weekly" | "monthly";

interface AnalyticsMaterializedResult {
  analytics: AnalyticsData;
  earliestTimestampMs: number | null;
}

interface ClickHouseTotalRow {
  total_conversations: number | string;
  total_input_tokens: number | string;
  total_output_tokens: number | string;
  total_cache_creation_tokens: number | string;
  total_cache_read_tokens: number | string;
  total_reasoning_tokens: number | string;
  total_tool_calls: number | string;
  total_failed_tool_calls: number | string;
  total_input_cost: number | string;
  total_output_cost: number | string;
  total_cache_write_cost: number | string;
  total_cache_read_cost: number | string;
  long_context_premium: number | string;
  long_context_conversations: number | string;
  earliest_timestamp_ms: number | string | null;
}

interface ClickHouseModelRow {
  provider: string;
  model_key: string;
  model_name: string;
  conversation_count: number | string;
  input_cost: number | string;
  output_cost: number | string;
  cache_write_cost: number | string;
  cache_read_cost: number | string;
  long_context_premium: number | string;
  long_context_conversations: number | string;
}

interface ClickHouseToolRow {
  provider: string;
  tool_name: string;
  tool_calls: number | string;
}

interface ClickHouseSubagentRow {
  provider: string;
  subagent_type: string;
  subagent_count: number | string;
}

interface ClickHouseBucketRow {
  bucket_start: string;
  provider: string;
  estimated_cost: number | string;
  input_tokens: number | string;
  output_tokens: number | string;
  cache_write_tokens: number | string;
  cache_read_tokens: number | string;
  reasoning_tokens: number | string;
  total_tokens: number | string;
  conversations: number | string;
  tool_calls: number | string;
  failed_tool_calls: number | string;
  subagents: number | string;
}

const DAY_MS = 24 * 60 * 60 * 1000;
const TIME_SERIES_KEYS: TimeSeriesKey[] = ["hourly", "daily", "weekly", "monthly"];
const CONVERSATION_STATE_PROVIDER_COLUMN = "`conversation_keys.provider`";
const CONVERSATION_STATE_CONVERSATION_ID_COLUMN = "`conversation_keys.conversation_id`";

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

function parseClickHouseBucketStart(value: string, key: TimeSeriesKey): Date {
  if (key === "hourly") {
    return new Date(value.replace(" ", "T"));
  }

  return parseClickHouseDateTime(value);
}

function getNextBucketStart(start: Date, key: TimeSeriesKey): Date {
  const next = new Date(start);
  switch (key) {
    case "hourly":
      next.setUTCHours(next.getUTCHours() + 1);
      break;
    case "daily":
      next.setUTCDate(next.getUTCDate() + 1);
      break;
    case "weekly":
      next.setUTCDate(next.getUTCDate() + 7);
      break;
    case "monthly":
      next.setUTCMonth(next.getUTCMonth() + 1, 1);
      break;
  }
  return next;
}

function formatBucketLabel(start: Date, key: TimeSeriesKey): string {
  if (key === "hourly") {
    return start.toISOString().slice(5, 13).replace("T", " ") + ":00";
  }
  if (key === "daily") {
    return start.toISOString().slice(0, 10);
  }
  if (key === "weekly") {
    return `Week of ${start.toISOString().slice(0, 10)}`;
  }
  return start.toISOString().slice(0, 7);
}

function createEmptyTimeSeriesPoint(
  start: Date,
  key: TimeSeriesKey
): AnalyticsTimeSeriesPoint {
  const end = getNextBucketStart(start, key);
  return {
    key: start.toISOString(),
    label: formatBucketLabel(start, key),
    start: start.toISOString(),
    end: end.toISOString(),
    estimatedCost: 0,
    claudeEstimatedCost: 0,
    codexEstimatedCost: 0,
    inputTokens: 0,
    outputTokens: 0,
    cacheWriteTokens: 0,
    cacheReadTokens: 0,
    reasoningTokens: 0,
    totalTokens: 0,
    conversations: 0,
    toolCalls: 0,
    failedToolCalls: 0,
    toolErrorRatePct: 0,
    subagents: 0,
    claudeInputTokens: 0,
    claudeOutputTokens: 0,
    claudeCacheWriteTokens: 0,
    claudeCacheReadTokens: 0,
    claudeReasoningTokens: 0,
    claudeTotalTokens: 0,
    claudeConversations: 0,
    claudeToolCalls: 0,
    claudeFailedToolCalls: 0,
    claudeToolErrorRatePct: 0,
    claudeSubagents: 0,
    codexInputTokens: 0,
    codexOutputTokens: 0,
    codexCacheWriteTokens: 0,
    codexCacheReadTokens: 0,
    codexReasoningTokens: 0,
    codexTotalTokens: 0,
    codexConversations: 0,
    codexToolCalls: 0,
    codexFailedToolCalls: 0,
    codexToolErrorRatePct: 0,
    codexSubagents: 0,
  };
}

function withToolErrorRates(
  point: AnalyticsTimeSeriesPoint
): AnalyticsTimeSeriesPoint {
  return {
    ...point,
    toolErrorRatePct:
      point.toolCalls > 0 ? (point.failedToolCalls / point.toolCalls) * 100 : 0,
    claudeToolErrorRatePct:
      point.claudeToolCalls > 0
        ? (point.claudeFailedToolCalls / point.claudeToolCalls) * 100
        : 0,
    codexToolErrorRatePct:
      point.codexToolCalls > 0
        ? (point.codexFailedToolCalls / point.codexToolCalls) * 100
        : 0,
  };
}

function buildRateValue(total: number, hours: number, days: number): AnalyticsRateValue {
  return {
    perHour: total / hours,
    perDay: total / days,
    perWeek: (total / days) * 7,
    perMonth: (total / days) * 30,
  };
}

function emptyCostBreakdown(): AnalyticsCostBreakdown {
  return {
    inputCost: 0,
    outputCost: 0,
    cacheWriteCost: 0,
    cacheReadCost: 0,
    longContextPremium: 0,
    longContextConversations: 0,
    totalCost: 0,
  };
}

function addCostBreakdown(
  target: AnalyticsCostBreakdown,
  source: AnalyticsCostBreakdown
): void {
  target.inputCost += source.inputCost;
  target.outputCost += source.outputCost;
  target.cacheWriteCost += source.cacheWriteCost;
  target.cacheReadCost += source.cacheReadCost;
  target.longContextPremium += source.longContextPremium;
  target.longContextConversations += source.longContextConversations;
  target.totalCost += source.totalCost;
}

function incrementProviderBreakdown(
  map: Record<string, ProviderBreakdown>,
  key: string,
  provider: string,
  count: number
): void {
  const providerKey = provider === "codex" ? "codex" : "claude";
  const existing = map[key] || { claude: 0, codex: 0 };
  existing[providerKey] += count;
  map[key] = existing;
}

function materializeTimeSeries(
  map: Map<string, AnalyticsTimeSeriesPoint>,
  key: TimeSeriesKey
): AnalyticsTimeSeriesPoint[] {
  const entries = Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  if (entries.length === 0) {
    return [];
  }

  const first = new Date(entries[0][0]);
  const last = new Date(entries[entries.length - 1][0]);
  const byKey = new Map(entries);
  const results: AnalyticsTimeSeriesPoint[] = [];

  for (let cursor = first; cursor <= last; cursor = getNextBucketStart(cursor, key)) {
    const bucketKey = cursor.toISOString();
    results.push(byKey.get(bucketKey) || createEmptyTimeSeriesPoint(cursor, key));
  }

  return results;
}

function mergeDailyUsageEntries(left: DailyUsage[], right: DailyUsage[]): DailyUsage[] {
  const combined = new Map<string, DailyUsage>();
  for (const entry of [...left, ...right]) {
    const existing =
      combined.get(entry.date) ||
      {
        date: entry.date,
        inputTokens: 0,
        outputTokens: 0,
        cacheWriteTokens: 0,
        cacheReadTokens: 0,
        conversations: 0,
        subagents: 0,
        claudeInputTokens: 0,
        claudeOutputTokens: 0,
        claudeCacheWriteTokens: 0,
        claudeCacheReadTokens: 0,
        codexInputTokens: 0,
        codexOutputTokens: 0,
        codexCacheWriteTokens: 0,
        codexCacheReadTokens: 0,
        claudeConversations: 0,
        codexConversations: 0,
        claudeSubagents: 0,
        codexSubagents: 0,
      };

    existing.inputTokens += entry.inputTokens;
    existing.outputTokens += entry.outputTokens;
    existing.cacheWriteTokens += entry.cacheWriteTokens;
    existing.cacheReadTokens += entry.cacheReadTokens;
    existing.conversations += entry.conversations;
    existing.subagents += entry.subagents;
    existing.claudeInputTokens += entry.claudeInputTokens;
    existing.claudeOutputTokens += entry.claudeOutputTokens;
    existing.claudeCacheWriteTokens += entry.claudeCacheWriteTokens;
    existing.claudeCacheReadTokens += entry.claudeCacheReadTokens;
    existing.codexInputTokens += entry.codexInputTokens;
    existing.codexOutputTokens += entry.codexOutputTokens;
    existing.codexCacheWriteTokens += entry.codexCacheWriteTokens;
    existing.codexCacheReadTokens += entry.codexCacheReadTokens;
    existing.claudeConversations += entry.claudeConversations;
    existing.codexConversations += entry.codexConversations;
    existing.claudeSubagents += entry.claudeSubagents;
    existing.codexSubagents += entry.codexSubagents;
    combined.set(entry.date, existing);
  }

  return Array.from(combined.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function mergeSimpleNumberMaps(
  left: Record<string, number>,
  right: Record<string, number>
): Record<string, number> {
  const merged: Record<string, number> = { ...left };
  for (const [key, value] of Object.entries(right)) {
    merged[key] = (merged[key] || 0) + value;
  }
  return merged;
}

function mergeProviderBreakdownMaps(
  left: Record<string, ProviderBreakdown>,
  right: Record<string, ProviderBreakdown>
): Record<string, ProviderBreakdown> {
  const merged: Record<string, ProviderBreakdown> = { ...left };
  for (const [key, value] of Object.entries(right)) {
    const existing = merged[key] || { claude: 0, codex: 0 };
    merged[key] = {
      claude: existing.claude + value.claude,
      codex: existing.codex + value.codex,
    };
  }
  return merged;
}

function mergeCostBreakdownMaps(
  left: AnalyticsCostBreakdownMap,
  right: AnalyticsCostBreakdownMap
): AnalyticsCostBreakdownMap {
  const merged: AnalyticsCostBreakdownMap = { ...left };
  for (const [key, value] of Object.entries(right)) {
    const existing = merged[key] || emptyCostBreakdown();
    addCostBreakdown(existing, value);
    merged[key] = existing;
  }
  return merged;
}

function mergeTimeSeries(
  left: AnalyticsTimeSeries,
  right: AnalyticsTimeSeries
): AnalyticsTimeSeries {
  const merged: AnalyticsTimeSeries = {
    hourly: [],
    daily: [],
    weekly: [],
    monthly: [],
  };

  for (const key of TIME_SERIES_KEYS) {
    const map = new Map<string, AnalyticsTimeSeriesPoint>();
    for (const point of [...left[key], ...right[key]]) {
      const existing = map.get(point.key) || createEmptyTimeSeriesPoint(new Date(point.start), key);
      existing.estimatedCost += point.estimatedCost;
      existing.claudeEstimatedCost += point.claudeEstimatedCost;
      existing.codexEstimatedCost += point.codexEstimatedCost;
      existing.inputTokens += point.inputTokens;
      existing.outputTokens += point.outputTokens;
      existing.cacheWriteTokens += point.cacheWriteTokens;
      existing.cacheReadTokens += point.cacheReadTokens;
      existing.reasoningTokens += point.reasoningTokens;
      existing.totalTokens += point.totalTokens;
      existing.conversations += point.conversations;
      existing.toolCalls += point.toolCalls;
      existing.failedToolCalls += point.failedToolCalls;
      existing.subagents += point.subagents;
      existing.claudeInputTokens += point.claudeInputTokens;
      existing.claudeOutputTokens += point.claudeOutputTokens;
      existing.claudeCacheWriteTokens += point.claudeCacheWriteTokens;
      existing.claudeCacheReadTokens += point.claudeCacheReadTokens;
      existing.claudeReasoningTokens += point.claudeReasoningTokens;
      existing.claudeTotalTokens += point.claudeTotalTokens;
      existing.claudeConversations += point.claudeConversations;
      existing.claudeToolCalls += point.claudeToolCalls;
      existing.claudeFailedToolCalls += point.claudeFailedToolCalls;
      existing.claudeSubagents += point.claudeSubagents;
      existing.codexInputTokens += point.codexInputTokens;
      existing.codexOutputTokens += point.codexOutputTokens;
      existing.codexCacheWriteTokens += point.codexCacheWriteTokens;
      existing.codexCacheReadTokens += point.codexCacheReadTokens;
      existing.codexReasoningTokens += point.codexReasoningTokens;
      existing.codexTotalTokens += point.codexTotalTokens;
      existing.codexConversations += point.codexConversations;
      existing.codexToolCalls += point.codexToolCalls;
      existing.codexFailedToolCalls += point.codexFailedToolCalls;
      existing.codexSubagents += point.codexSubagents;
      map.set(point.key, existing);
    }
    merged[key] = materializeTimeSeries(map, key).map(withToolErrorRates);
  }

  return merged;
}

function buildRates(
  analytics: AnalyticsData,
  days?: number,
  earliestTimestampMs?: number | null
): AnalyticsRates {
  const windowEnd = Date.now();
  const windowStart = days
    ? windowEnd - days * DAY_MS
    : earliestTimestampMs ?? windowEnd;
  const durationMs = Math.max(windowEnd - windowStart, 60 * 60 * 1000);
  const durationHours = Math.max(durationMs / (60 * 60 * 1000), 1);
  const durationDays = Math.max(durationMs / DAY_MS, 1 / 24);
  const totalTokens =
    analytics.totalInputTokens +
    analytics.totalOutputTokens +
    analytics.totalCacheCreationTokens +
    analytics.totalCacheReadTokens +
    analytics.totalReasoningTokens;

  return {
    spend: buildRateValue(analytics.estimatedCost, durationHours, durationDays),
    totalTokens: buildRateValue(totalTokens, durationHours, durationDays),
    inputTokens: buildRateValue(
      analytics.totalInputTokens,
      durationHours,
      durationDays
    ),
    outputTokens: buildRateValue(
      analytics.totalOutputTokens,
      durationHours,
      durationDays
    ),
    cacheWriteTokens: buildRateValue(
      analytics.totalCacheCreationTokens,
      durationHours,
      durationDays
    ),
    cacheReadTokens: buildRateValue(
      analytics.totalCacheReadTokens,
      durationHours,
      durationDays
    ),
    reasoningTokens: buildRateValue(
      analytics.totalReasoningTokens,
      durationHours,
      durationDays
    ),
    conversations: buildRateValue(
      analytics.totalConversations,
      durationHours,
      durationDays
    ),
    toolCalls: buildRateValue(
      analytics.totalToolCalls,
      durationHours,
      durationDays
    ),
    failedToolCalls: buildRateValue(
      analytics.totalFailedToolCalls,
      durationHours,
      durationDays
    ),
    subagents: buildRateValue(
      Object.values(analytics.subagentTypeBreakdown).reduce((sum, count) => sum + count, 0),
      durationHours,
      durationDays
    ),
  };
}

function buildEmptyAnalytics(days?: number): AnalyticsMaterializedResult {
  return {
    analytics: buildAnalyticsFromConversations([], days),
    earliestTimestampMs: null,
  };
}

function buildBucketExpression(key: TimeSeriesKey): string {
  switch (key) {
    case "hourly":
      return "toStartOfHour(toTimeZone(fc.conversation_time, 'UTC'))";
    case "daily":
      return "toStartOfDay(fc.conversation_time, 'UTC')";
    case "weekly":
      return "toStartOfWeek(fc.conversation_time, 1, 'UTC')";
    case "monthly":
      return "toStartOfMonth(fc.conversation_time, 'UTC')";
  }
}

function buildLongContextPremiumSql(modelExpr: string, inputTokensExpr: string): string {
  return `if(
    ${inputTokensExpr} > 200000 AND (
      positionCaseInsensitiveUTF8(${modelExpr}, 'opus-4-6') > 0 OR
      positionCaseInsensitiveUTF8(${modelExpr}, 'opus-4-5') > 0 OR
      positionCaseInsensitiveUTF8(${modelExpr}, 'sonnet-4-6') > 0 OR
      positionCaseInsensitiveUTF8(${modelExpr}, 'sonnet-4-5') > 0 OR
      positionCaseInsensitiveUTF8(${modelExpr}, 'sonnet-4') > 0
    ),
    fc.estimated_input_cost + (fc.estimated_output_cost * 0.5) + fc.estimated_cache_write_cost + fc.estimated_cache_read_cost,
    0
  )`;
}

function buildConversationStateWhereClauses(
  provider?: string,
  startIso?: string,
  endIso?: string,
  tableAlias?: string
): string[] {
  const prefix = tableAlias ? `${tableAlias}.` : "";
  const providerExpression = `${prefix}${CONVERSATION_STATE_PROVIDER_COLUMN}`;
  const conversationTimeExpression = `coalesce(${prefix}started_at, ${prefix}first_message_time, ${prefix}last_event_at)`;
  const whereClauses = [`${conversationTimeExpression} IS NOT NULL`];
  if (startIso) {
    whereClauses.push(
      `${conversationTimeExpression} >= parseDateTime64BestEffort('${escapeClickHouseString(
        startIso
      )}')`
    );
  }
  if (endIso) {
    whereClauses.push(
      `${conversationTimeExpression} < parseDateTime64BestEffort('${escapeClickHouseString(
        endIso
      )}')`
    );
  }
  if (provider === "claude" || provider === "codex") {
    whereClauses.push(`${providerExpression} = '${escapeClickHouseString(provider)}'`);
  }

  return whereClauses;
}

function buildFilteredConversationCtes(
  provider?: string,
  startIso?: string,
  endIso?: string
): string {
  const database = getClickHouseSettings().database;
  const whereClauses = buildConversationStateWhereClauses(provider, startIso, endIso);

  return `
WITH filtered_conversations AS (
  SELECT
    ${CONVERSATION_STATE_PROVIDER_COLUMN} AS provider,
    ${CONVERSATION_STATE_CONVERSATION_ID_COLUMN} AS conversation_id,
    coalesce(started_at, first_message_time, last_event_at) AS conversation_time,
    nullIf(latest_model, '') AS model_name,
    toInt64(ifNull(total_input_tokens, 0)) AS total_input_tokens,
    toInt64(ifNull(total_output_tokens, 0)) AS total_output_tokens,
    toInt64(ifNull(total_cache_write_tokens, 0)) AS total_cache_creation_tokens,
    toInt64(ifNull(total_cache_read_tokens, 0)) AS total_cache_read_tokens,
    toInt64(ifNull(total_reasoning_tokens, 0)) AS total_reasoning_tokens,
    toInt64(ifNull(tool_call_count, 0)) AS total_tool_calls,
    toInt64(ifNull(subagent_count, 0)) AS total_subagents,
    toFloat64(ifNull(estimated_input_cost, 0)) AS estimated_input_cost,
    toFloat64(ifNull(estimated_output_cost, 0)) AS estimated_output_cost,
    toFloat64(ifNull(estimated_cache_write_cost, 0)) AS estimated_cache_write_cost,
    toFloat64(ifNull(estimated_cache_read_cost, 0)) AS estimated_cache_read_cost
  FROM ${database}.conversation_state
  WHERE ${whereClauses.join("\n    AND ")}
)`;
}

function buildFilteredConversationsSubquery(
  provider?: string,
  startIso?: string,
  endIso?: string
): string {
  const database = getClickHouseSettings().database;
  const whereClauses = buildConversationStateWhereClauses(provider, startIso, endIso);

  return `(
  SELECT
    ${CONVERSATION_STATE_PROVIDER_COLUMN} AS provider,
    ${CONVERSATION_STATE_CONVERSATION_ID_COLUMN} AS conversation_id,
    coalesce(started_at, first_message_time, last_event_at) AS conversation_time,
    nullIf(latest_model, '') AS model_name,
    toInt64(ifNull(total_input_tokens, 0)) AS total_input_tokens,
    toInt64(ifNull(total_output_tokens, 0)) AS total_output_tokens,
    toInt64(ifNull(total_cache_write_tokens, 0)) AS total_cache_creation_tokens,
    toInt64(ifNull(total_cache_read_tokens, 0)) AS total_cache_read_tokens,
    toInt64(ifNull(total_reasoning_tokens, 0)) AS total_reasoning_tokens,
    toInt64(ifNull(tool_call_count, 0)) AS total_tool_calls,
    toInt64(ifNull(subagent_count, 0)) AS total_subagents,
    toFloat64(ifNull(estimated_input_cost, 0)) AS estimated_input_cost,
    toFloat64(ifNull(estimated_output_cost, 0)) AS estimated_output_cost,
    toFloat64(ifNull(estimated_cache_write_cost, 0)) AS estimated_cache_write_cost,
    toFloat64(ifNull(estimated_cache_read_cost, 0)) AS estimated_cache_read_cost
  FROM ${database}.conversation_state
  WHERE ${whereClauses.join("\n    AND ")}
)`;
}

function buildFailedToolCallsSubquery(
  provider?: string,
  startIso?: string,
  endIso?: string
): string {
  const database = getClickHouseSettings().database;
  const whereClauses = buildConversationStateWhereClauses(provider, startIso, endIso);

  return `(
  SELECT
    te.provider AS provider,
    te.conversation_id AS conversation_id,
    countIf(te.error_text != '') AS failed_tool_call_count
  FROM ${database}.tool_events AS te
  WHERE (te.provider, te.conversation_id) IN (
    SELECT
      ${CONVERSATION_STATE_PROVIDER_COLUMN} AS provider,
      ${CONVERSATION_STATE_CONVERSATION_ID_COLUMN} AS conversation_id
    FROM ${database}.conversation_state
    WHERE ${whereClauses.join("\n      AND ")}
  )
  GROUP BY te.provider, te.conversation_id
)`;
}

function buildCostBreakdown(row: {
  inputCost: number;
  outputCost: number;
  cacheWriteCost: number;
  cacheReadCost: number;
  longContextPremium: number;
  longContextConversations: number;
}): AnalyticsCostBreakdown {
  return {
    inputCost: row.inputCost,
    outputCost: row.outputCost,
    cacheWriteCost: row.cacheWriteCost,
    cacheReadCost: row.cacheReadCost,
    longContextPremium: row.longContextPremium,
    longContextConversations: row.longContextConversations,
    totalCost:
      row.inputCost +
      row.outputCost +
      row.cacheWriteCost +
      row.cacheReadCost +
      row.longContextPremium,
  };
}

function buildDailyUsage(rows: ClickHouseBucketRow[]): DailyUsage[] {
  const dailyMap = new Map<string, DailyUsage>();

  for (const row of rows) {
    const date = parseClickHouseDateTime(row.bucket_start).toISOString().slice(0, 10);
    const provider = row.provider === "codex" ? "codex" : "claude";
    const existing =
      dailyMap.get(date) ||
      {
        date,
        inputTokens: 0,
        outputTokens: 0,
        cacheWriteTokens: 0,
        cacheReadTokens: 0,
        conversations: 0,
        subagents: 0,
        claudeInputTokens: 0,
        claudeOutputTokens: 0,
        claudeCacheWriteTokens: 0,
        claudeCacheReadTokens: 0,
        codexInputTokens: 0,
        codexOutputTokens: 0,
        codexCacheWriteTokens: 0,
        codexCacheReadTokens: 0,
        claudeConversations: 0,
        codexConversations: 0,
        claudeSubagents: 0,
        codexSubagents: 0,
      };

    const inputTokens = toNumber(row.input_tokens);
    const outputTokens = toNumber(row.output_tokens);
    const cacheWriteTokens = toNumber(row.cache_write_tokens);
    const cacheReadTokens = toNumber(row.cache_read_tokens);
    const conversations = toNumber(row.conversations);
    const subagents = toNumber(row.subagents);

    existing.inputTokens += inputTokens;
    existing.outputTokens += outputTokens;
    existing.cacheWriteTokens += cacheWriteTokens;
    existing.cacheReadTokens += cacheReadTokens;
    existing.conversations += conversations;
    existing.subagents += subagents;

    if (provider === "claude") {
      existing.claudeInputTokens += inputTokens;
      existing.claudeOutputTokens += outputTokens;
      existing.claudeCacheWriteTokens += cacheWriteTokens;
      existing.claudeCacheReadTokens += cacheReadTokens;
      existing.claudeConversations += conversations;
      existing.claudeSubagents += subagents;
    } else {
      existing.codexInputTokens += inputTokens;
      existing.codexOutputTokens += outputTokens;
      existing.codexCacheWriteTokens += cacheWriteTokens;
      existing.codexCacheReadTokens += cacheReadTokens;
      existing.codexConversations += conversations;
      existing.codexSubagents += subagents;
    }

    dailyMap.set(date, existing);
  }

  return Array.from(dailyMap.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function buildTimeSeries(
  rows: ClickHouseBucketRow[],
  key: TimeSeriesKey
): AnalyticsTimeSeriesPoint[] {
  const map = new Map<string, AnalyticsTimeSeriesPoint>();

  for (const row of rows) {
    const bucketStart = parseClickHouseBucketStart(row.bucket_start, key);
    const bucketId = bucketStart.toISOString();
    const provider = row.provider === "codex" ? "codex" : "claude";
    const point = map.get(bucketId) || createEmptyTimeSeriesPoint(bucketStart, key);
    const estimatedCost = toNumber(row.estimated_cost);
    const inputTokens = toNumber(row.input_tokens);
    const outputTokens = toNumber(row.output_tokens);
    const cacheWriteTokens = toNumber(row.cache_write_tokens);
    const cacheReadTokens = toNumber(row.cache_read_tokens);
    const reasoningTokens = toNumber(row.reasoning_tokens);
    const totalTokens = toNumber(row.total_tokens);
    const conversations = toNumber(row.conversations);
    const toolCalls = toNumber(row.tool_calls);
    const failedToolCalls = toNumber(row.failed_tool_calls);
    const subagents = toNumber(row.subagents);

    point.estimatedCost += estimatedCost;
    point.inputTokens += inputTokens;
    point.outputTokens += outputTokens;
    point.cacheWriteTokens += cacheWriteTokens;
    point.cacheReadTokens += cacheReadTokens;
    point.reasoningTokens += reasoningTokens;
    point.totalTokens += totalTokens;
    point.conversations += conversations;
    point.toolCalls += toolCalls;
    point.failedToolCalls += failedToolCalls;
    point.subagents += subagents;

    if (provider === "claude") {
      point.claudeEstimatedCost += estimatedCost;
      point.claudeInputTokens += inputTokens;
      point.claudeOutputTokens += outputTokens;
      point.claudeCacheWriteTokens += cacheWriteTokens;
      point.claudeCacheReadTokens += cacheReadTokens;
      point.claudeReasoningTokens += reasoningTokens;
      point.claudeTotalTokens += totalTokens;
      point.claudeConversations += conversations;
      point.claudeToolCalls += toolCalls;
      point.claudeFailedToolCalls += failedToolCalls;
      point.claudeSubagents += subagents;
    } else {
      point.codexEstimatedCost += estimatedCost;
      point.codexInputTokens += inputTokens;
      point.codexOutputTokens += outputTokens;
      point.codexCacheWriteTokens += cacheWriteTokens;
      point.codexCacheReadTokens += cacheReadTokens;
      point.codexReasoningTokens += reasoningTokens;
      point.codexTotalTokens += totalTokens;
      point.codexConversations += conversations;
      point.codexToolCalls += toolCalls;
      point.codexFailedToolCalls += failedToolCalls;
      point.codexSubagents += subagents;
    }

    map.set(bucketId, point);
  }

  return materializeTimeSeries(map, key).map(withToolErrorRates);
}

function mergeAnalyticsResults(
  left: AnalyticsMaterializedResult,
  right: AnalyticsMaterializedResult,
  days?: number
): AnalyticsMaterializedResult {
  const costBreakdown = emptyCostBreakdown();
  addCostBreakdown(costBreakdown, left.analytics.costBreakdown);
  addCostBreakdown(costBreakdown, right.analytics.costBreakdown);

  const analytics: AnalyticsData = {
    totalConversations:
      left.analytics.totalConversations + right.analytics.totalConversations,
    totalInputTokens: left.analytics.totalInputTokens + right.analytics.totalInputTokens,
    totalOutputTokens:
      left.analytics.totalOutputTokens + right.analytics.totalOutputTokens,
    totalCacheCreationTokens:
      left.analytics.totalCacheCreationTokens +
      right.analytics.totalCacheCreationTokens,
    totalCacheReadTokens:
      left.analytics.totalCacheReadTokens + right.analytics.totalCacheReadTokens,
    totalReasoningTokens:
      left.analytics.totalReasoningTokens + right.analytics.totalReasoningTokens,
    totalToolCalls: left.analytics.totalToolCalls + right.analytics.totalToolCalls,
    totalFailedToolCalls:
      left.analytics.totalFailedToolCalls + right.analytics.totalFailedToolCalls,
    modelBreakdown: mergeSimpleNumberMaps(
      left.analytics.modelBreakdown,
      right.analytics.modelBreakdown
    ),
    toolBreakdown: mergeSimpleNumberMaps(
      left.analytics.toolBreakdown,
      right.analytics.toolBreakdown
    ),
    subagentTypeBreakdown: mergeSimpleNumberMaps(
      left.analytics.subagentTypeBreakdown,
      right.analytics.subagentTypeBreakdown
    ),
    modelBreakdownByProvider: mergeProviderBreakdownMaps(
      left.analytics.modelBreakdownByProvider,
      right.analytics.modelBreakdownByProvider
    ),
    toolBreakdownByProvider: mergeProviderBreakdownMaps(
      left.analytics.toolBreakdownByProvider,
      right.analytics.toolBreakdownByProvider
    ),
    subagentTypeBreakdownByProvider: mergeProviderBreakdownMaps(
      left.analytics.subagentTypeBreakdownByProvider,
      right.analytics.subagentTypeBreakdownByProvider
    ),
    dailyUsage: mergeDailyUsageEntries(left.analytics.dailyUsage, right.analytics.dailyUsage),
    rates: left.analytics.rates,
    timeSeries: mergeTimeSeries(left.analytics.timeSeries, right.analytics.timeSeries),
    estimatedCost: left.analytics.estimatedCost + right.analytics.estimatedCost,
    costBreakdown,
    costBreakdownByProvider: mergeCostBreakdownMaps(
      left.analytics.costBreakdownByProvider,
      right.analytics.costBreakdownByProvider
    ),
    costBreakdownByModel: mergeCostBreakdownMaps(
      left.analytics.costBreakdownByModel,
      right.analytics.costBreakdownByModel
    ),
  };
  const earliestTimestampMs = [left.earliestTimestampMs, right.earliestTimestampMs]
    .filter((value): value is number => typeof value === "number")
    .reduce<number | null>((min, value) => (min === null ? value : Math.min(min, value)), null);

  analytics.rates = buildRates(analytics, days, earliestTimestampMs);

  return {
    analytics,
    earliestTimestampMs,
  };
}

async function getLegacyTodayAnalytics(
  days?: number,
  provider?: string
): Promise<AnalyticsMaterializedResult> {
  const conversations = filterAnalyticsConversationsByProvider(
    await listRawConversations(undefined, days, { dayScope: "today" }),
    provider
  );
  const earliestTimestampMs =
    conversations.length > 0
      ? Math.min(...conversations.map((conversation) => conversation.timestamp))
      : null;

  return {
    analytics: buildAnalyticsFromConversations(conversations, days),
    earliestTimestampMs,
  };
}

async function queryBucketRows(
  key: TimeSeriesKey,
  provider?: string,
  startIso?: string,
  endIso?: string
): Promise<ClickHouseBucketRow[]> {
  const bucketExpression = buildBucketExpression(key);
  const longContextPremiumSql = buildLongContextPremiumSql("fc.model_name", "fc.total_input_tokens");
  const failedToolCallsSubquery = buildFailedToolCallsSubquery(provider, startIso, endIso);
  const filteredConversationsSubquery = buildFilteredConversationsSubquery(
    provider,
    startIso,
    endIso
  );
  const sql = `
SELECT
  bucket_start,
  conversation_provider AS provider,
  sum(estimated_cost) AS estimated_cost,
  sum(input_tokens) AS input_tokens,
  sum(output_tokens) AS output_tokens,
  sum(cache_write_tokens) AS cache_write_tokens,
  sum(cache_read_tokens) AS cache_read_tokens,
  sum(reasoning_tokens) AS reasoning_tokens,
  sum(total_tokens) AS total_tokens,
  sum(conversations) AS conversations,
  sum(tool_calls) AS tool_calls,
  sum(failed_tool_calls) AS failed_tool_calls,
  sum(subagents) AS subagents
FROM (
  SELECT
    ${bucketExpression} AS bucket_start,
    fc.provider AS conversation_provider,
    fc.estimated_input_cost +
      fc.estimated_output_cost +
      fc.estimated_cache_write_cost +
      fc.estimated_cache_read_cost +
      ${longContextPremiumSql} AS estimated_cost,
    fc.total_input_tokens AS input_tokens,
    fc.total_output_tokens AS output_tokens,
    fc.total_cache_creation_tokens AS cache_write_tokens,
    fc.total_cache_read_tokens AS cache_read_tokens,
    fc.total_reasoning_tokens AS reasoning_tokens,
    fc.total_input_tokens +
      fc.total_output_tokens +
      fc.total_cache_creation_tokens +
      fc.total_cache_read_tokens +
      fc.total_reasoning_tokens AS total_tokens,
    toInt64(1) AS conversations,
    fc.total_tool_calls AS tool_calls,
    toInt64(ifNull(ft.failed_tool_call_count, 0)) AS failed_tool_calls,
    fc.total_subagents AS subagents
  FROM ${filteredConversationsSubquery} AS fc
  LEFT JOIN ${failedToolCallsSubquery} AS ft
    ON fc.provider = ft.provider
   AND fc.conversation_id = ft.conversation_id
)
GROUP BY bucket_start, conversation_provider
ORDER BY bucket_start ASC, conversation_provider ASC`;

  return queryClickHouseRows<ClickHouseBucketRow>(sql);
}

export async function queryClickHouseAnalytics(
  days?: number,
  provider?: string,
  options?: {
    includeLiveToday?: boolean;
  }
): Promise<AnalyticsMaterializedResult> {
  const database = getClickHouseSettings().database;
  const windowStartIso = days ? new Date(Date.now() - days * DAY_MS).toISOString() : undefined;
  const windowEndIso = options?.includeLiveToday
    ? undefined
    : new Date(startOfTodayMs()).toISOString();
  const conversationKeyWhere = buildConversationStateWhereClauses(
    provider,
    windowStartIso,
    windowEndIso
  );

  if (windowStartIso && windowEndIso && windowStartIso >= windowEndIso) {
    return buildEmptyAnalytics(days);
  }

  const longContextPremiumSql = buildLongContextPremiumSql("fc.model_name", "fc.total_input_tokens");
  const failedToolCallsSubquery = buildFailedToolCallsSubquery(
    provider,
    windowStartIso,
    windowEndIso
  );
  const filteredConversationsSubquery = buildFilteredConversationsSubquery(
    provider,
    windowStartIso,
    windowEndIso
  );
  const totalsSql = `
SELECT
  count() AS total_conversations,
  sum(fc.total_input_tokens) AS total_input_tokens,
  sum(fc.total_output_tokens) AS total_output_tokens,
  sum(fc.total_cache_creation_tokens) AS total_cache_creation_tokens,
  sum(fc.total_cache_read_tokens) AS total_cache_read_tokens,
  sum(fc.total_reasoning_tokens) AS total_reasoning_tokens,
  sum(fc.total_tool_calls) AS total_tool_calls,
  sum(toInt64(ifNull(ft.failed_tool_call_count, 0))) AS total_failed_tool_calls,
  sum(fc.estimated_input_cost) AS total_input_cost,
  sum(fc.estimated_output_cost) AS total_output_cost,
  sum(fc.estimated_cache_write_cost) AS total_cache_write_cost,
  sum(fc.estimated_cache_read_cost) AS total_cache_read_cost,
  sum(${longContextPremiumSql}) AS long_context_premium,
  sum(toInt64(${longContextPremiumSql} > 0)) AS long_context_conversations,
  min(toUnixTimestamp64Milli(fc.conversation_time)) AS earliest_timestamp_ms
FROM ${filteredConversationsSubquery} AS fc
LEFT JOIN ${failedToolCallsSubquery} AS ft
  ON fc.provider = ft.provider
 AND fc.conversation_id = ft.conversation_id`;
  const modelSql = `
SELECT
  provider,
  model_key,
  model_name,
  conversation_count,
  input_cost,
  output_cost,
  cache_write_cost,
  cache_read_cost,
  long_context_premium,
  long_context_conversations
FROM (
  SELECT
    fc.provider AS provider,
    ifNull(fc.model_name, 'unknown') AS model_key,
    ifNull(fc.model_name, '') AS model_name,
    count() AS conversation_count,
    sum(fc.estimated_input_cost) AS input_cost,
    sum(fc.estimated_output_cost) AS output_cost,
    sum(fc.estimated_cache_write_cost) AS cache_write_cost,
    sum(fc.estimated_cache_read_cost) AS cache_read_cost,
    sum(${longContextPremiumSql}) AS long_context_premium,
    sum(toInt64(${longContextPremiumSql} > 0)) AS long_context_conversations
  FROM ${filteredConversationsSubquery} AS fc
  GROUP BY
    fc.provider,
    ifNull(fc.model_name, 'unknown'),
    ifNull(fc.model_name, '')
)
ORDER BY model_key ASC, provider ASC`;
  const toolSql = `
${buildFilteredConversationCtes(provider, windowStartIso, windowEndIso)}
SELECT
  te.provider AS provider,
  te.tool_name AS tool_name,
  count() AS tool_calls
FROM ${database}.tool_events AS te
WHERE (te.provider, te.conversation_id) IN (
  SELECT
    ${CONVERSATION_STATE_PROVIDER_COLUMN} AS provider,
    ${CONVERSATION_STATE_CONVERSATION_ID_COLUMN} AS conversation_id
  FROM ${database}.conversation_state
  WHERE ${conversationKeyWhere.join("\n    AND ")}
)
GROUP BY te.provider, te.tool_name
ORDER BY te.tool_name ASC, te.provider ASC`;
  const subagentSql = `
${buildFilteredConversationCtes(provider, windowStartIso, windowEndIso)}
SELECT
  te.provider AS provider,
  te.subagent_type AS subagent_type,
  count() AS subagent_count
FROM ${database}.tool_events AS te
WHERE te.subagent_type != ''
  AND (te.provider, te.conversation_id) IN (
    SELECT
      ${CONVERSATION_STATE_PROVIDER_COLUMN} AS provider,
      ${CONVERSATION_STATE_CONVERSATION_ID_COLUMN} AS conversation_id
    FROM ${database}.conversation_state
    WHERE ${conversationKeyWhere.join("\n      AND ")}
  )
GROUP BY te.provider, te.subagent_type
ORDER BY te.subagent_type ASC, te.provider ASC`;

  const [
    totalRows,
    modelRows,
    toolRows,
    subagentRows,
    hourlyRows,
    dailyRows,
    weeklyRows,
    monthlyRows,
  ] = await Promise.all([
    queryClickHouseRows<ClickHouseTotalRow>(totalsSql),
    queryClickHouseRows<ClickHouseModelRow>(modelSql),
    queryClickHouseRows<ClickHouseToolRow>(toolSql),
    queryClickHouseRows<ClickHouseSubagentRow>(subagentSql),
    queryBucketRows("hourly", provider, windowStartIso, windowEndIso),
    queryBucketRows("daily", provider, windowStartIso, windowEndIso),
    queryBucketRows("weekly", provider, windowStartIso, windowEndIso),
    queryBucketRows("monthly", provider, windowStartIso, windowEndIso),
  ]);

  const totals = totalRows[0];
  if (!totals) {
    return buildEmptyAnalytics(days);
  }

  const modelBreakdown: Record<string, number> = {};
  const modelBreakdownByProvider: Record<string, ProviderBreakdown> = {};
  const costBreakdownByProvider: AnalyticsCostBreakdownMap = {};
  const costBreakdownByModel: AnalyticsCostBreakdownMap = {};

  for (const row of modelRows) {
    const conversationCount = toNumber(row.conversation_count);
    const costBreakdown = buildCostBreakdown({
      inputCost: toNumber(row.input_cost),
      outputCost: toNumber(row.output_cost),
      cacheWriteCost: toNumber(row.cache_write_cost),
      cacheReadCost: toNumber(row.cache_read_cost),
      longContextPremium: toNumber(row.long_context_premium),
      longContextConversations: toNumber(row.long_context_conversations),
    });

    const providerKey = row.provider === "codex" ? "codex" : "claude";
    const providerCost = costBreakdownByProvider[providerKey] || emptyCostBreakdown();
    addCostBreakdown(providerCost, costBreakdown);
    costBreakdownByProvider[providerKey] = providerCost;

    const modelCost = costBreakdownByModel[row.model_key] || emptyCostBreakdown();
    addCostBreakdown(modelCost, costBreakdown);
    costBreakdownByModel[row.model_key] = modelCost;

    if (row.model_name) {
      modelBreakdown[row.model_name] = (modelBreakdown[row.model_name] || 0) + conversationCount;
      incrementProviderBreakdown(
        modelBreakdownByProvider,
        row.model_name,
        providerKey,
        conversationCount
      );
    }
  }

  const toolBreakdown: Record<string, number> = {};
  const toolBreakdownByProvider: Record<string, ProviderBreakdown> = {};
  for (const row of toolRows) {
    const toolCalls = toNumber(row.tool_calls);
    toolBreakdown[row.tool_name] = (toolBreakdown[row.tool_name] || 0) + toolCalls;
    incrementProviderBreakdown(
      toolBreakdownByProvider,
      row.tool_name,
      row.provider,
      toolCalls
    );
  }

  const subagentTypeBreakdown: Record<string, number> = {};
  const subagentTypeBreakdownByProvider: Record<string, ProviderBreakdown> = {};
  for (const row of subagentRows) {
    const subagentCount = toNumber(row.subagent_count);
    subagentTypeBreakdown[row.subagent_type] =
      (subagentTypeBreakdown[row.subagent_type] || 0) + subagentCount;
    incrementProviderBreakdown(
      subagentTypeBreakdownByProvider,
      row.subagent_type,
      row.provider,
      subagentCount
    );
  }

  const costBreakdown = buildCostBreakdown({
    inputCost: toNumber(totals.total_input_cost),
    outputCost: toNumber(totals.total_output_cost),
    cacheWriteCost: toNumber(totals.total_cache_write_cost),
    cacheReadCost: toNumber(totals.total_cache_read_cost),
    longContextPremium: toNumber(totals.long_context_premium),
    longContextConversations: toNumber(totals.long_context_conversations),
  });
  const timeSeries: AnalyticsTimeSeries = {
    hourly: buildTimeSeries(hourlyRows, "hourly"),
    daily: buildTimeSeries(dailyRows, "daily"),
    weekly: buildTimeSeries(weeklyRows, "weekly"),
    monthly: buildTimeSeries(monthlyRows, "monthly"),
  };
  const analytics: AnalyticsData = {
    totalConversations: toNumber(totals.total_conversations),
    totalInputTokens: toNumber(totals.total_input_tokens),
    totalOutputTokens: toNumber(totals.total_output_tokens),
    totalCacheCreationTokens: toNumber(totals.total_cache_creation_tokens),
    totalCacheReadTokens: toNumber(totals.total_cache_read_tokens),
    totalReasoningTokens: toNumber(totals.total_reasoning_tokens),
    totalToolCalls: toNumber(totals.total_tool_calls),
    totalFailedToolCalls: toNumber(totals.total_failed_tool_calls),
    modelBreakdown,
    toolBreakdown,
    subagentTypeBreakdown,
    modelBreakdownByProvider,
    toolBreakdownByProvider,
    subagentTypeBreakdownByProvider,
    dailyUsage: buildDailyUsage(dailyRows),
    rates: {
      spend: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      totalTokens: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      inputTokens: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      outputTokens: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      cacheWriteTokens: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      cacheReadTokens: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      reasoningTokens: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      conversations: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      toolCalls: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      failedToolCalls: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
      subagents: { perHour: 0, perDay: 0, perWeek: 0, perMonth: 0 },
    },
    timeSeries,
    estimatedCost: costBreakdown.totalCost,
    costBreakdown,
    costBreakdownByProvider,
    costBreakdownByModel,
  };
  const earliestTimestampMs =
    totals.earliest_timestamp_ms === null ? null : toNumber(totals.earliest_timestamp_ms);

  analytics.rates = buildRates(analytics, days, earliestTimestampMs);

  return {
    analytics,
    earliestTimestampMs,
  };
}

export async function queryClickHouseAnalyticsWithLiveFallback(
  days?: number,
  provider?: string,
  options?: {
    liveIngestionEnabled?: boolean;
  }
): Promise<AnalyticsMaterializedResult> {
  const historical = await queryClickHouseAnalytics(days, provider, {
    includeLiveToday: options?.liveIngestionEnabled,
  });

  if (options?.liveIngestionEnabled) {
    return historical;
  }

  const liveToday = await getLegacyTodayAnalytics(days, provider);
  return mergeAnalyticsResults(historical, liveToday, days);
}
