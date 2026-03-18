import type {
  AnalyticsCostBreakdown,
  AnalyticsData,
  AnalyticsRateValue,
  AnalyticsRates,
  AnalyticsTimeSeries,
  AnalyticsTimeSeriesPoint,
  ConversationEvaluation,
  ContextAnalytics,
  ContextBucket,
  ContextStep,
  ContextWindowStats,
  ConversationDag,
  ConversationDagStats,
  ConversationDagSummary,
  ConversationPlan,
  ConversationPlanStep,
  ConversationSummary,
  DatabaseArtifactStatus,
  DatabaseColumnSchema,
  DatabaseStatus,
  DatabaseTableSchema,
  DailyUsage,
  DisplayBlock,
  EvaluationPrompt,
  HistoryEntry,
  PlanDetail,
  PlanSummary,
  ProcessedConversation,
  ProcessedMessage,
  ProjectInfo,
  ProviderBreakdown,
  SubagentInfo,
  SubscriptionSettings,
  TokenUsage,
} from "@/lib/types";

type JsonRecord = Record<string, unknown>;

function snakeToCamel(value: string): string {
  return value.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

function camelToSnake(value: string): string {
  return value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

function asRecord(value: unknown): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return {};
  }

  const record = value as JsonRecord;

  return new Proxy(record, {
    get(target, prop, receiver) {
      if (typeof prop !== "string") {
        return Reflect.get(target, prop, receiver);
      }

      if (Reflect.has(target, prop)) {
        return Reflect.get(target, prop, receiver);
      }

      const alternateKey = prop.includes("_") ? snakeToCamel(prop) : camelToSnake(prop);
      if (alternateKey !== prop && Reflect.has(target, alternateKey)) {
        return Reflect.get(target, alternateKey, receiver);
      }

      return undefined;
    },
  });
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringOr(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function nullableString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function numberOr(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  return fallback;
}

function booleanOr(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function field(item: JsonRecord, ...keys: string[]): unknown {
  for (const key of keys) {
    if (key in item) {
      return item[key];
    }
  }

  return undefined;
}

function normalizeThreadType(value: unknown): "main" | "subagent" {
  return value === "subagent" ? "subagent" : "main";
}

function normalizeMessageRole(value: unknown): "user" | "assistant" {
  return value === "user" ? "user" : "assistant";
}

function normalizeUsage(value: unknown): TokenUsage {
  const item = asRecord(value);
  return {
    input_tokens: numberOr(item.input_tokens),
    output_tokens: numberOr(item.output_tokens),
    cache_creation_input_tokens: numberOr(item.cache_creation_tokens),
    cache_read_input_tokens: numberOr(item.cache_read_tokens),
  };
}

function normalizeConversationPlanSteps(value: unknown): ConversationPlanStep[] {
  return asArray(value).map((step) => {
    const item = asRecord(step);
    return {
      step: stringOr(item.step),
      status: stringOr(item.status),
    };
  });
}

function normalizeConversationPlan(value: unknown): ConversationPlan {
  const item = asRecord(value);
  return {
    id: stringOr(item.id),
    slug: stringOr(item.slug),
    title: stringOr(item.title),
    preview: stringOr(item.preview),
    content: stringOr(item.content),
    provider: stringOr(item.provider) === "codex" ? "codex" : "claude",
    timestamp: numberOr(item.timestamp),
    sessionId: stringOr(item.session_id),
    projectPath: stringOr(item.project_path),
    model: nullableString(item.model),
    sourcePath: nullableString(item.source_path),
    explanation: nullableString(item.explanation),
    steps: normalizeConversationPlanSteps(item.steps),
  };
}

function normalizeBlock(value: unknown): DisplayBlock {
  const item = asRecord(value);
  const type = stringOr(item.type);

  if (type === "thinking") {
    return {
      type: "thinking",
      thinking: stringOr(item.thinking),
      charCount: numberOr(item.char_count),
    };
  }

  if (type === "tool_call") {
    return {
      type: "tool_call",
      toolUseId: stringOr(item.tool_use_id),
      toolName: stringOr(item.tool_name),
      input: asRecord(item.input),
      result: nullableString(item.result),
      isError: typeof item.is_error === "boolean" ? item.is_error : undefined,
    };
  }

  return {
    type: "text",
    text: stringOr(item.text),
  };
}

function normalizeMessage(value: unknown): ProcessedMessage {
  const item = asRecord(value);
  return {
    id: stringOr(item.id),
    role: normalizeMessageRole(item.role),
    timestamp: numberOr(item.timestamp),
    blocks: asArray(item.blocks).map(normalizeBlock),
    usage: item.usage ? normalizeUsage(item.usage) : undefined,
    model: nullableString(item.model),
    reasoningTokens:
      item.reasoning_tokens === undefined ? undefined : numberOr(item.reasoning_tokens),
    speed: nullableString(item.speed),
  };
}

function normalizeSubagent(value: unknown): SubagentInfo {
  const item = asRecord(value);
  return {
    agentId: stringOr(item.agent_id),
    description: nullableString(item.description),
    subagentType: nullableString(item.subagent_type),
    nickname: nullableString(item.nickname),
    hasFile: booleanOr(item.has_file),
    projectPath: stringOr(item.project_path),
    sessionId: stringOr(item.session_id),
  };
}

function normalizeContextBucket(value: unknown): ContextBucket {
  const item = asRecord(value);
  return {
    label: stringOr(item.label),
    category:
      stringOr(item.category) as ContextBucket["category"],
    inputTokens: numberOr(item.input_tokens),
    outputTokens: numberOr(item.output_tokens),
    cacheWriteTokens: numberOr(item.cache_write_tokens),
    cacheReadTokens: numberOr(item.cache_read_tokens),
    totalTokens: numberOr(item.total_tokens),
    calls: numberOr(item.calls),
  };
}

function normalizeContextStep(value: unknown): ContextStep {
  const item = asRecord(value);
  return {
    messageId: stringOr(item.message_id),
    index: numberOr(item.index),
    role: normalizeMessageRole(item.role),
    label: stringOr(item.label),
    category: stringOr(item.category) as ContextStep["category"],
    timestamp: numberOr(item.timestamp),
    inputTokens: numberOr(item.input_tokens),
    outputTokens: numberOr(item.output_tokens),
    cacheWriteTokens: numberOr(item.cache_write_tokens),
    cacheReadTokens: numberOr(item.cache_read_tokens),
    totalTokens: numberOr(item.total_tokens),
  };
}

function normalizeContextAnalytics(value: unknown): ContextAnalytics {
  const item = asRecord(value);
  return {
    buckets: asArray(item.buckets).map(normalizeContextBucket),
    steps: asArray(item.steps).map(normalizeContextStep),
  };
}

function normalizeContextWindow(value: unknown): ContextWindowStats {
  const item = asRecord(value);
  return {
    peakContextWindow: numberOr(item.peak_context_window),
    apiCalls: numberOr(item.api_calls),
    cumulativeTokens: numberOr(item.cumulative_tokens),
  };
}

export function normalizeConversationSummary(value: unknown): ConversationSummary {
  const item = asRecord(value);
  return {
    sessionId: stringOr(item.session_id),
    projectPath: stringOr(item.project_path),
    projectName: stringOr(item.project_name),
    threadType: normalizeThreadType(item.thread_type),
    firstMessage: stringOr(item.first_message),
    timestamp: numberOr(item.timestamp),
    createdAt: numberOr(item.created_at),
    lastUpdatedAt: numberOr(item.last_updated_at),
    isRunning: booleanOr(item.is_running),
    messageCount: numberOr(item.message_count),
    model: nullableString(item.model),
    totalInputTokens: numberOr(item.total_input_tokens),
    totalOutputTokens: numberOr(item.total_output_tokens),
    totalCacheCreationTokens: numberOr(item.total_cache_creation_tokens),
    totalCacheReadTokens: numberOr(item.total_cache_read_tokens),
    toolUseCount: numberOr(item.tool_use_count),
    failedToolCallCount: numberOr(item.failed_tool_call_count),
    toolBreakdown: asRecord(item.tool_breakdown) as Record<string, number>,
    subagentCount: numberOr(item.subagent_count),
    subagentTypeBreakdown: asRecord(item.subagent_type_breakdown) as Record<string, number>,
    taskCount: numberOr(item.task_count),
    gitBranch: nullableString(item.git_branch),
    reasoningEffort: nullableString(item.reasoning_effort),
    speed: nullableString(item.speed),
    totalReasoningTokens:
      item.total_reasoning_tokens === undefined ? undefined : numberOr(item.total_reasoning_tokens),
  };
}

export function normalizeConversations(value: unknown): ConversationSummary[] {
  return asArray(value).map(normalizeConversationSummary);
}

function normalizeConversationDagStats(value: unknown): ConversationDagStats {
  const item = asRecord(value);
  return {
    totalNodes: numberOr(item.total_nodes),
    totalEdges: numberOr(item.total_edges),
    totalSubagentNodes: numberOr(item.total_subagent_nodes),
    maxDepth: numberOr(item.max_depth),
    maxBreadth: numberOr(item.max_breadth),
    leafCount: numberOr(item.leaf_count),
    rootSubagentCount: numberOr(item.root_subagent_count),
    totalMessages: numberOr(item.total_messages),
    totalTokens: numberOr(item.total_tokens),
  };
}

function normalizeConversationDagNode(value: unknown): ConversationDag["nodes"][number] {
  const item = asRecord(value);
  return {
    id: stringOr(item.id),
    sessionId: stringOr(item.session_id),
    parentSessionId: nullableString(item.parent_session_id),
    projectPath: stringOr(item.project_path),
    label: stringOr(item.label),
    description: nullableString(item.description),
    nickname: nullableString(item.nickname),
    subagentType: nullableString(item.subagent_type),
    threadType: normalizeThreadType(item.thread_type),
    hasTranscript: booleanOr(item.has_transcript),
    model: nullableString(item.model),
    messageCount: numberOr(item.message_count),
    totalTokens: numberOr(item.total_tokens),
    timestamp: numberOr(item.timestamp),
    depth: numberOr(item.depth),
    path: stringOr(item.path),
    isRoot: booleanOr(item.is_root),
  };
}

export function normalizeConversationDag(value: unknown): ConversationDag {
  const item = asRecord(value);
  return {
    projectPath: stringOr(item.project_path),
    rootSessionId: stringOr(item.root_session_id),
    nodes: asArray(item.nodes).map(normalizeConversationDagNode),
    edges: asArray(item.edges).map((edge) => {
      const normalized = asRecord(edge);
      return {
        id: stringOr(normalized.id),
        source: stringOr(normalized.source),
        target: stringOr(normalized.target),
      };
    }),
    stats: normalizeConversationDagStats(item.stats),
  };
}

export function normalizeConversationDagSummaries(value: unknown): ConversationDagSummary[] {
  return asArray(value).map((entry) => {
    const item = asRecord(entry);
    return {
      ...normalizeConversationSummary(item),
      dag: normalizeConversationDagStats(item.dag),
    };
  });
}

export function normalizeConversationDetail(value: unknown): ProcessedConversation {
  const item = asRecord(value);
  return {
    sessionId: stringOr(item.session_id),
    projectPath: stringOr(item.project_path),
    createdAt: numberOr(item.created_at),
    lastUpdatedAt: numberOr(item.last_updated_at),
    isRunning: booleanOr(item.is_running),
    messages: asArray(item.messages).map(normalizeMessage),
    plans: asArray(item.plans).map(normalizeConversationPlan),
    totalUsage: normalizeUsage(item.total_usage),
    model: nullableString(item.model),
    gitBranch: nullableString(item.git_branch),
    startTime: numberOr(item.start_time),
    endTime: numberOr(item.end_time),
    subagents: asArray(item.subagents).map(normalizeSubagent),
    contextAnalytics: normalizeContextAnalytics(item.context_analytics),
    contextWindow: normalizeContextWindow(item.context_window),
    reasoningEffort: nullableString(item.reasoning_effort),
    speed: nullableString(item.speed),
    totalReasoningTokens:
      item.total_reasoning_tokens === undefined ? undefined : numberOr(item.total_reasoning_tokens),
  };
}

function normalizePlanSummary(value: unknown): PlanSummary {
  const item = asRecord(value);
  return {
    id: stringOr(item.id),
    slug: stringOr(item.slug),
    title: stringOr(item.title),
    preview: stringOr(item.preview),
    provider: stringOr(item.provider) === "codex" ? "codex" : "claude",
    timestamp: numberOr(item.timestamp),
    model: nullableString(item.model),
    sourcePath: nullableString(item.source_path),
    sessionId: nullableString(item.session_id),
    projectPath: nullableString(item.project_path),
  };
}

export function normalizePlans(value: unknown): PlanSummary[] {
  return asArray(value).map(normalizePlanSummary);
}

export function normalizePlan(value: unknown): PlanDetail {
  const item = asRecord(value);
  return {
    id: stringOr(item.id),
    slug: stringOr(item.slug),
    title: stringOr(item.title),
    content: stringOr(item.content),
    provider: stringOr(item.provider) === "codex" ? "codex" : "claude",
    timestamp: numberOr(item.timestamp),
    model: nullableString(item.model),
    sourcePath: nullableString(item.source_path),
    sessionId: nullableString(item.session_id),
    projectPath: nullableString(item.project_path),
  };
}

export function normalizeProjects(value: unknown): ProjectInfo[] {
  return asArray(value).map((entry) => {
    const item = asRecord(entry);
    return {
      encodedPath: stringOr(item.encoded_path),
      displayName: stringOr(item.display_name),
      fullPath: stringOr(item.full_path),
      sessionCount: numberOr(item.session_count),
      lastActivity: numberOr(item.last_activity),
    };
  });
}

function normalizeCostBreakdown(value: unknown): AnalyticsCostBreakdown {
  const item = asRecord(value);
  return {
    inputCost: numberOr(item.input_cost),
    outputCost: numberOr(item.output_cost),
    cacheWriteCost: numberOr(item.cache_write_cost),
    cacheReadCost: numberOr(item.cache_read_cost),
    longContextPremium: numberOr(item.long_context_premium),
    longContextConversations: numberOr(item.long_context_conversations),
    totalCost: numberOr(item.total_cost),
  };
}

function normalizeProviderBreakdown(value: unknown): ProviderBreakdown {
  const item = asRecord(value);
  return {
    claude: numberOr(item.claude),
    codex: numberOr(item.codex),
  };
}

function normalizeRateValue(value: unknown): AnalyticsRateValue {
  const item = asRecord(value);
  return {
    perHour: numberOr(item.per_hour),
    perDay: numberOr(item.per_day),
    perWeek: numberOr(item.per_week),
    perMonth: numberOr(item.per_month),
  };
}

function normalizeRates(value: unknown): AnalyticsRates {
  const item = asRecord(value);
  return {
    spend: normalizeRateValue(item.spend),
    totalTokens: normalizeRateValue(item.total_tokens),
    inputTokens: normalizeRateValue(item.input_tokens),
    outputTokens: normalizeRateValue(item.output_tokens),
    cacheWriteTokens: normalizeRateValue(item.cache_write_tokens),
    cacheReadTokens: normalizeRateValue(item.cache_read_tokens),
    reasoningTokens: normalizeRateValue(item.reasoning_tokens),
    conversations: normalizeRateValue(item.conversations),
    toolCalls: normalizeRateValue(item.tool_calls),
    failedToolCalls: normalizeRateValue(item.failed_tool_calls),
    subagents: normalizeRateValue(item.subagents),
  };
}

function normalizeTimeSeriesPoint(value: unknown): AnalyticsTimeSeriesPoint {
  const item = asRecord(value);
  return {
    key: stringOr(item.key),
    label: stringOr(item.label),
    start: stringOr(item.start),
    end: stringOr(item.end),
    estimatedCost: numberOr(item.estimated_cost),
    claudeEstimatedCost: numberOr(item.claude_estimated_cost),
    codexEstimatedCost: numberOr(item.codex_estimated_cost),
    inputTokens: numberOr(item.input_tokens),
    outputTokens: numberOr(item.output_tokens),
    cacheWriteTokens: numberOr(item.cache_write_tokens),
    cacheReadTokens: numberOr(item.cache_read_tokens),
    reasoningTokens: numberOr(item.reasoning_tokens),
    totalTokens: numberOr(item.total_tokens),
    conversations: numberOr(item.conversations),
    toolCalls: numberOr(item.tool_calls),
    failedToolCalls: numberOr(item.failed_tool_calls),
    toolErrorRatePct: numberOr(item.tool_error_rate_pct),
    subagents: numberOr(item.subagents),
    claudeInputTokens: numberOr(item.claude_input_tokens),
    claudeOutputTokens: numberOr(item.claude_output_tokens),
    claudeCacheWriteTokens: numberOr(item.claude_cache_write_tokens),
    claudeCacheReadTokens: numberOr(item.claude_cache_read_tokens),
    claudeReasoningTokens: numberOr(item.claude_reasoning_tokens),
    claudeTotalTokens: numberOr(item.claude_total_tokens),
    claudeConversations: numberOr(item.claude_conversations),
    claudeToolCalls: numberOr(item.claude_tool_calls),
    claudeFailedToolCalls: numberOr(item.claude_failed_tool_calls),
    claudeToolErrorRatePct: numberOr(item.claude_tool_error_rate_pct),
    claudeSubagents: numberOr(item.claude_subagents),
    codexInputTokens: numberOr(item.codex_input_tokens),
    codexOutputTokens: numberOr(item.codex_output_tokens),
    codexCacheWriteTokens: numberOr(item.codex_cache_write_tokens),
    codexCacheReadTokens: numberOr(item.codex_cache_read_tokens),
    codexReasoningTokens: numberOr(item.codex_reasoning_tokens),
    codexTotalTokens: numberOr(item.codex_total_tokens),
    codexConversations: numberOr(item.codex_conversations),
    codexToolCalls: numberOr(item.codex_tool_calls),
    codexFailedToolCalls: numberOr(item.codex_failed_tool_calls),
    codexToolErrorRatePct: numberOr(item.codex_tool_error_rate_pct),
    codexSubagents: numberOr(item.codex_subagents),
  };
}

function normalizeTimeSeries(value: unknown): AnalyticsTimeSeries {
  const item = asRecord(value);
  return {
    hourly: asArray(item.hourly).map(normalizeTimeSeriesPoint),
    daily: asArray(item.daily).map(normalizeTimeSeriesPoint),
    weekly: asArray(item.weekly).map(normalizeTimeSeriesPoint),
    monthly: asArray(item.monthly).map(normalizeTimeSeriesPoint),
  };
}

function normalizeDailyUsage(value: unknown): DailyUsage {
  const item = asRecord(value);
  return {
    date: stringOr(item.date),
    inputTokens: numberOr(item.input_tokens),
    outputTokens: numberOr(item.output_tokens),
    cacheWriteTokens: numberOr(item.cache_write_tokens),
    cacheReadTokens: numberOr(item.cache_read_tokens),
    conversations: numberOr(item.conversations),
    subagents: numberOr(item.subagents),
    claudeInputTokens: numberOr(item.claude_input_tokens),
    claudeOutputTokens: numberOr(item.claude_output_tokens),
    claudeCacheWriteTokens: numberOr(item.claude_cache_write_tokens),
    claudeCacheReadTokens: numberOr(item.claude_cache_read_tokens),
    codexInputTokens: numberOr(item.codex_input_tokens),
    codexOutputTokens: numberOr(item.codex_output_tokens),
    codexCacheWriteTokens: numberOr(item.codex_cache_write_tokens),
    codexCacheReadTokens: numberOr(item.codex_cache_read_tokens),
    claudeConversations: numberOr(item.claude_conversations),
    codexConversations: numberOr(item.codex_conversations),
    claudeSubagents: numberOr(item.claude_subagents),
    codexSubagents: numberOr(item.codex_subagents),
  };
}

export function normalizeAnalytics(value: unknown): AnalyticsData {
  const item = asRecord(value);
  const modelBreakdownByProvider = asRecord(item.model_breakdown_by_provider);
  const toolBreakdownByProvider = asRecord(item.tool_breakdown_by_provider);
  const subagentTypeBreakdownByProvider = asRecord(item.subagent_type_breakdown_by_provider);
  const costBreakdownByProvider = asRecord(item.cost_breakdown_by_provider);
  const costBreakdownByModel = asRecord(item.cost_breakdown_by_model);

  return {
    totalConversations: numberOr(item.total_conversations),
    totalInputTokens: numberOr(item.total_input_tokens),
    totalOutputTokens: numberOr(item.total_output_tokens),
    totalCacheCreationTokens: numberOr(item.total_cache_creation_tokens),
    totalCacheReadTokens: numberOr(item.total_cache_read_tokens),
    totalReasoningTokens: numberOr(item.total_reasoning_tokens),
    totalToolCalls: numberOr(item.total_tool_calls),
    totalFailedToolCalls: numberOr(item.total_failed_tool_calls),
    modelBreakdown: asRecord(item.model_breakdown) as Record<string, number>,
    toolBreakdown: asRecord(item.tool_breakdown) as Record<string, number>,
    subagentTypeBreakdown: asRecord(item.subagent_type_breakdown) as Record<string, number>,
    modelBreakdownByProvider: Object.fromEntries(
      Object.entries(modelBreakdownByProvider).map(([key, entry]) => [
        key,
        normalizeProviderBreakdown(entry),
      ])
    ),
    toolBreakdownByProvider: Object.fromEntries(
      Object.entries(toolBreakdownByProvider).map(([key, entry]) => [
        key,
        normalizeProviderBreakdown(entry),
      ])
    ),
    subagentTypeBreakdownByProvider: Object.fromEntries(
      Object.entries(subagentTypeBreakdownByProvider).map(([key, entry]) => [
        key,
        normalizeProviderBreakdown(entry),
      ])
    ),
    dailyUsage: asArray(item.daily_usage).map(normalizeDailyUsage),
    rates: normalizeRates(item.rates),
    timeSeries: normalizeTimeSeries(item.time_series),
    estimatedCost: numberOr(item.estimated_cost),
    costBreakdown: normalizeCostBreakdown(item.cost_breakdown),
    costBreakdownByProvider: Object.fromEntries(
      Object.entries(costBreakdownByProvider).map(([key, entry]) => [
        key,
        normalizeCostBreakdown(entry),
      ])
    ),
    costBreakdownByModel: Object.fromEntries(
      Object.entries(costBreakdownByModel).map(([key, entry]) => [
        key,
        normalizeCostBreakdown(entry),
      ])
    ),
  };
}

export function normalizeHistory(value: unknown): HistoryEntry[] {
  return asArray(value).map((entry) => {
    const item = asRecord(entry);
    return {
      display: stringOr(item.display),
      pastedContents:
        item.pasted_contents && typeof item.pasted_contents === "object"
          ? (item.pasted_contents as Record<string, unknown>)
          : undefined,
      timestamp: numberOr(item.timestamp),
      project: nullableString(item.project),
    };
  });
}

function normalizeDatabaseColumn(value: unknown): DatabaseColumnSchema {
  const item = asRecord(value);
  return {
    name: stringOr(field(item, "name")),
    type: stringOr(field(item, "type")),
    nullable: booleanOr(field(item, "nullable")),
    defaultValue:
      field(item, "defaultValue", "default_value") === null
        ? null
        : nullableString(field(item, "defaultValue", "default_value")),
    isPrimaryKey: booleanOr(field(item, "isPrimaryKey", "is_primary_key")),
    references:
      field(item, "references") === null
        ? null
        : nullableString(field(item, "references")),
  };
}

function normalizeDatabaseTable(value: unknown): DatabaseTableSchema {
  const item = asRecord(value);
  return {
    name: stringOr(field(item, "name")),
    rowCount: numberOr(field(item, "rowCount", "row_count")),
    columns: asArray(field(item, "columns")).map(normalizeDatabaseColumn),
  };
}

function normalizeDatabaseArtifact(value: unknown): DatabaseArtifactStatus {
  const item = asRecord(value);
  return {
    key: stringOr(field(item, "key")) as DatabaseArtifactStatus["key"],
    label: stringOr(field(item, "label")),
    engine: stringOr(field(item, "engine")),
    role: stringOr(field(item, "role")) as DatabaseArtifactStatus["role"],
    availability: stringOr(field(item, "availability")) as DatabaseArtifactStatus["availability"],
    note:
      field(item, "note") === null ? null : nullableString(field(item, "note")),
    error:
      field(item, "error") === null ? null : nullableString(field(item, "error")),
    path: field(item, "path") === null ? null : nullableString(field(item, "path")),
    target: field(item, "target") === null ? null : nullableString(field(item, "target")),
    publicPath:
      field(item, "publicPath", "public_path") === null
        ? null
        : nullableString(field(item, "publicPath", "public_path")),
    docsUrl:
      field(item, "docsUrl", "docs_url") === null
        ? null
        : nullableString(field(item, "docsUrl", "docs_url")),
    tableCount: numberOr(field(item, "tableCount", "table_count")),
    tables: asArray(field(item, "tables")).map(normalizeDatabaseTable),
  };
}

export function normalizeDatabaseStatus(value: unknown): DatabaseStatus {
  const item = asRecord(value);
  const runtime = asRecord(field(item, "runtime"));
  const databases = asRecord(field(item, "databases"));
  return {
    status: stringOr(field(item, "status")) as DatabaseStatus["status"],
    trigger: nullableString(field(item, "trigger")),
    startedAt:
      field(item, "startedAt", "started_at") === null
        ? null
        : nullableString(field(item, "startedAt", "started_at")),
    finishedAt:
      field(item, "finishedAt", "finished_at") === null
        ? null
        : nullableString(field(item, "finishedAt", "finished_at")),
    durationMs:
      field(item, "durationMs", "duration_ms") === null
        ? null
        : numberOr(field(item, "durationMs", "duration_ms")),
    error: field(item, "error") === null ? null : nullableString(field(item, "error")),
    lastSuccessfulRefreshAt:
      field(item, "lastSuccessfulRefreshAt", "last_successful_refresh_at") === null
        ? null
        : nullableString(field(item, "lastSuccessfulRefreshAt", "last_successful_refresh_at")),
    idempotencyKey:
      field(item, "idempotencyKey", "idempotency_key") === null
        ? null
        : nullableString(field(item, "idempotencyKey", "idempotency_key")),
    scopeLabel: stringOr(field(item, "scopeLabel", "scope_label")),
    windowDays: numberOr(field(item, "windowDays", "window_days")),
    windowStart:
      field(item, "windowStart", "window_start") === null
        ? null
        : nullableString(field(item, "windowStart", "window_start")),
    windowEnd:
      field(item, "windowEnd", "window_end") === null
        ? null
        : nullableString(field(item, "windowEnd", "window_end")),
    sourceConversationCount: numberOr(
      field(item, "sourceConversationCount", "source_conversation_count")
    ),
    refreshIntervalMinutes: numberOr(
      field(item, "refreshIntervalMinutes", "refresh_interval_minutes"),
      360
    ),
    runtime: {
      analyticsReadBackend: stringOr(
        field(runtime, "analyticsReadBackend", "analytics_read_backend")
      ) as DatabaseStatus["runtime"]["analyticsReadBackend"],
      conversationSummaryReadBackend: stringOr(
        field(
          runtime,
          "conversationSummaryReadBackend",
          "conversation_summary_read_backend"
        )
      ) as DatabaseStatus["runtime"]["conversationSummaryReadBackend"],
    },
    databases: {
      sqlite: normalizeDatabaseArtifact(field(databases, "sqlite")),
      legacyDuckdb: normalizeDatabaseArtifact(
        field(databases, "legacyDuckdb", "legacy_duckdb")
      ),
    },
  };
}

function normalizeEvaluationPrompt(value: unknown): EvaluationPrompt {
  const item = asRecord(value);
  return {
    promptId: stringOr(field(item, "promptId", "prompt_id")),
    name: stringOr(field(item, "name")),
    description:
      field(item, "description") === null
        ? null
        : nullableString(field(item, "description")),
    promptText: stringOr(field(item, "promptText", "prompt_text")),
    isDefault: booleanOr(field(item, "isDefault", "is_default")),
    createdAt: stringOr(field(item, "createdAt", "created_at")),
    updatedAt: stringOr(field(item, "updatedAt", "updated_at")),
  };
}

export function normalizeEvaluationPrompts(value: unknown): EvaluationPrompt[] {
  return asArray(value).map(normalizeEvaluationPrompt);
}

function normalizeConversationEvaluation(value: unknown): ConversationEvaluation {
  const item = asRecord(value);
  return {
    evaluationId: stringOr(field(item, "evaluationId", "evaluation_id")),
    conversationId: stringOr(field(item, "conversationId", "conversation_id")),
    promptId:
      field(item, "promptId", "prompt_id") === null
        ? null
        : nullableString(field(item, "promptId", "prompt_id")),
    provider: stringOr(field(item, "provider")) as ConversationEvaluation["provider"],
    model: stringOr(field(item, "model")),
    status: stringOr(field(item, "status")) as ConversationEvaluation["status"],
    scope: stringOr(field(item, "scope")) as ConversationEvaluation["scope"],
    selectionInstruction:
      field(item, "selectionInstruction", "selection_instruction") === null
        ? null
        : nullableString(field(item, "selectionInstruction", "selection_instruction")),
    promptName: stringOr(field(item, "promptName", "prompt_name")),
    promptText: stringOr(field(item, "promptText", "prompt_text")),
    reportMarkdown:
      field(item, "reportMarkdown", "report_markdown") === null
        ? null
        : nullableString(field(item, "reportMarkdown", "report_markdown")),
    rawOutput:
      field(item, "rawOutput", "raw_output") === null
        ? null
        : nullableString(field(item, "rawOutput", "raw_output")),
    errorMessage:
      field(item, "errorMessage", "error_message") === null
        ? null
        : nullableString(field(item, "errorMessage", "error_message")),
    command: stringOr(field(item, "command")),
    createdAt: stringOr(field(item, "createdAt", "created_at")),
    finishedAt:
      field(item, "finishedAt", "finished_at") === null
        ? null
        : nullableString(field(item, "finishedAt", "finished_at")),
    durationMs:
      field(item, "durationMs", "duration_ms") === null
        ? null
        : numberOr(field(item, "durationMs", "duration_ms")),
  };
}

export function normalizeConversationEvaluations(value: unknown): ConversationEvaluation[] {
  return asArray(value).map(normalizeConversationEvaluation);
}

function normalizeProviderSubscription(value: unknown): SubscriptionSettings["claude"] {
  const item = asRecord(value);
  return {
    provider: stringOr(field(item, "provider")) as SubscriptionSettings["claude"]["provider"],
    hasSubscription: booleanOr(field(item, "hasSubscription", "has_subscription")),
    monthlyCost: numberOr(field(item, "monthlyCost", "monthly_cost")),
    updatedAt: stringOr(field(item, "updatedAt", "updated_at")),
  };
}

export function normalizeSubscriptionSettings(value: unknown): SubscriptionSettings {
  const item = asRecord(value);
  return {
    claude: normalizeProviderSubscription(field(item, "claude")),
    codex: normalizeProviderSubscription(field(item, "codex")),
  };
}

export function normalizeTasks(value: unknown): unknown[] {
  const item = asRecord(value);
  return asArray(item.tasks);
}
