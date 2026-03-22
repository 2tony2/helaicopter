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
  ConversationRouteResolution,
  ConversationSummary,
  DatabaseArtifactStatus,
  DatabaseColumnSchema,
  DatabaseLoadMetric,
  DatabaseStatus,
  DatabaseTableSchema,
  DailyUsage,
  DisplayBlock,
  EvaluationPrompt,
  HistoryEntry,
  OrchestrationDag,
  OrchestrationDagNode,
  OrchestrationFeatureBranch,
  OrchestrationInvocation,
  OrchestrationOperationHistoryEntry,
  OrchestrationFinalPullRequest,
  OrchestrationRunEvaluation,
  OrchestrationRunEvaluationConversation,
  OrchestrationReviewSummary,
  OrchestrationTaskRecord,
  OrchestrationTaskPullRequest,
  OvernightOatsRunRecord,
  PrefectDeploymentRecord,
  PrefectFlowRunRecord,
  PrefectOatsMetadata,
  PrefectWorkPoolRecord,
  PrefectWorkerRecord,
  PlanDetail,
  PlanSummary,
  ProcessedConversation,
  ProcessedMessage,
  ProjectInfo,
  FrontendProvider,
  ProviderBreakdown,
  SubagentInfo,
  SubscriptionSettings,
  TokenUsage,
} from "@/lib/types";
import type { DatabaseArtifactPayload, DatabaseStatusPayload } from "./schemas/database.ts";
import type {
  ConversationSummaryPayload,
} from "./schemas/conversations.ts";
import type {
  ConversationEvaluationPayload,
  EvaluationPromptPayload,
} from "./schemas/evaluations.ts";
import type { SubscriptionSettingsPayload } from "./schemas/subscriptions.ts";
import { providerSchema } from "./schemas/shared.ts";

/**
 * Compatibility shim for the FastAPI rollout: frontend callers now target the
 * Python API directly, but normalization still accepts both snake_case FastAPI
 * payloads and the legacy camelCase Next.js shapes during the transition.
 */
type JsonRecord = Record<string, unknown>;
type PresentDatabaseArtifactPayload = Exclude<
  DatabaseStatusPayload["databases"][keyof DatabaseStatusPayload["databases"]],
  undefined
>;
type SnakeDatabaseArtifactPayload = Extract<PresentDatabaseArtifactPayload, { table_count: number }>;
type CamelDatabaseArtifactPayload = Extract<PresentDatabaseArtifactPayload, { tableCount: number }>;

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

function normalizeProvider(value: unknown): FrontendProvider {
  return providerSchema.parse(value);
}

function normalizeOptionalProvider(value: unknown): FrontendProvider | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }

  return normalizeProvider(value);
}

function nullableString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function nullableStringOrNull(value: unknown): string | null | undefined {
  if (value === null) {
    return null;
  }

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

function nullableNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  return undefined;
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

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function basename(value?: string): string | undefined {
  if (!value) return undefined;
  const cleaned = value.replace(/\/+$/, "");
  const segments = cleaned.split("/").filter(Boolean);
  return segments[segments.length - 1];
}

function toRepoHref(path?: string, repoRoot?: string): string | undefined {
  if (!path || !repoRoot) return undefined;
  const normalizedPath = trimTrailingSlash(path);
  const normalizedRoot = trimTrailingSlash(repoRoot);
  if (!normalizedPath.startsWith(normalizedRoot)) {
    return undefined;
  }

  const relativePath = normalizedPath.slice(normalizedRoot.length);
  return relativePath ? relativePath : "/";
}

function normalizePrefectRunTone(value?: string): PrefectFlowRunRecord["statusTone"] {
  const normalized = value?.toUpperCase();
  if (normalized === "RUNNING" || normalized === "PENDING") {
    return "running";
  }
  if (normalized === "COMPLETED") {
    return "success";
  }
  if (
    normalized === "FAILED" ||
    normalized === "CRASHED" ||
    normalized === "CANCELLED" ||
    normalized === "CANCELLING"
  ) {
    return "error";
  }
  if (normalized === "SCHEDULED" || normalized === "PAUSED") {
    return "pending";
  }
  return "unknown";
}

function normalizeInfraTone(value?: string): PrefectWorkerRecord["statusTone"] {
  const normalized = value?.toUpperCase();
  if (normalized === "ONLINE" || normalized === "READY") {
    return "healthy";
  }
  if (normalized === "OFFLINE") {
    return "offline";
  }
  if (normalized === "PAUSED" || normalized === "NOT_READY") {
    return "warning";
  }
  return "unknown";
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
    provider: normalizeProvider(item.provider),
    timestamp: numberOr(item.timestamp),
    sessionId: stringOr(item.session_id),
    projectPath: stringOr(item.project_path),
    routeSlug: nullableStringOrNull(item.route_slug),
    conversationRef: nullableStringOrNull(item.conversation_ref),
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
    routeSlug: nullableStringOrNull(item.route_slug),
    conversationRef: nullableStringOrNull(item.conversation_ref),
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

function normalizeConversationSummaryRecord(item: JsonRecord): ConversationSummary {
  return {
    sessionId: stringOr(item.session_id),
    projectPath: stringOr(item.project_path),
    projectName: stringOr(item.project_name),
    routeSlug: nullableString(field(item, "routeSlug", "route_slug")),
    conversationRef: nullableString(field(item, "conversationRef", "conversation_ref")),
    threadType: normalizeThreadType(item.thread_type),
    firstMessage: stringOr(item.first_message),
    timestamp: numberOr(item.timestamp),
    createdAt: numberOr(item.created_at),
    lastUpdatedAt: numberOr(item.last_updated_at),
    isRunning: booleanOr(item.is_running),
    messageCount: numberOr(item.message_count),
    model: nullableString(item.model) ?? undefined,
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
    gitBranch: nullableString(item.git_branch) ?? undefined,
    reasoningEffort: nullableString(item.reasoning_effort) ?? undefined,
    speed: nullableString(item.speed) ?? undefined,
    totalReasoningTokens:
      item.total_reasoning_tokens === undefined ? undefined : numberOr(item.total_reasoning_tokens),
  };
}

export function normalizeConversationSummary(
  value: ConversationSummaryPayload
): ConversationSummary {
  const isCamel = "sessionId" in value;

  return {
    sessionId: isCamel ? value.sessionId : value.session_id,
    projectPath: isCamel ? value.projectPath : value.project_path,
    projectName: isCamel ? value.projectName : value.project_name,
    provider: normalizeOptionalProvider((value as JsonRecord).provider),
    routeSlug: isCamel ? value.routeSlug : value.route_slug,
    conversationRef: isCamel ? value.conversationRef : value.conversation_ref,
    threadType: isCamel ? value.threadType : value.thread_type,
    firstMessage: isCamel ? value.firstMessage : value.first_message,
    timestamp: value.timestamp,
    createdAt: isCamel ? value.createdAt : value.created_at,
    lastUpdatedAt: isCamel ? value.lastUpdatedAt : value.last_updated_at,
    isRunning: isCamel ? value.isRunning : value.is_running,
    messageCount: isCamel ? value.messageCount : value.message_count,
    model: value.model ?? undefined,
    totalInputTokens: isCamel ? value.totalInputTokens : value.total_input_tokens,
    totalOutputTokens: isCamel ? value.totalOutputTokens : value.total_output_tokens,
    totalCacheCreationTokens: isCamel
      ? value.totalCacheCreationTokens
      : value.total_cache_creation_tokens,
    totalCacheReadTokens: isCamel
      ? value.totalCacheReadTokens
      : value.total_cache_read_tokens,
    toolUseCount: isCamel ? value.toolUseCount : value.tool_use_count,
    failedToolCallCount: isCamel
      ? value.failedToolCallCount
      : value.failed_tool_call_count,
    toolBreakdown: isCamel ? value.toolBreakdown : value.tool_breakdown,
    subagentCount: isCamel ? value.subagentCount : value.subagent_count,
    subagentTypeBreakdown: isCamel
      ? value.subagentTypeBreakdown
      : value.subagent_type_breakdown,
    taskCount: isCamel ? value.taskCount : value.task_count,
    gitBranch: (isCamel ? value.gitBranch : value.git_branch) ?? undefined,
    reasoningEffort:
      (isCamel ? value.reasoningEffort : value.reasoning_effort) ?? undefined,
    speed: value.speed ?? undefined,
    totalReasoningTokens: (
      isCamel ? value.totalReasoningTokens : value.total_reasoning_tokens
    ) ?? undefined,
  };
}

export function normalizeConversations(
  value: ConversationSummaryPayload[]
): ConversationSummary[] {
  return value.map(normalizeConversationSummary);
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
    path: item.path === null ? null : nullableString(item.path),
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
      ...normalizeConversationSummaryRecord(item),
      dag: normalizeConversationDagStats(item.dag),
    };
  });
}

export function normalizeConversationDetail(value: unknown): ProcessedConversation {
  const item = asRecord(value);
  return {
    sessionId: stringOr(item.session_id),
    projectPath: stringOr(item.project_path),
    provider: normalizeOptionalProvider(item.provider),
    routeSlug: nullableString(item.route_slug),
    conversationRef: nullableString(item.conversation_ref),
    threadType:
      item.thread_type === undefined ? undefined : normalizeThreadType(item.thread_type),
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
    provider: normalizeProvider(item.provider),
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
    provider: normalizeProvider(item.provider),
    timestamp: numberOr(item.timestamp),
    model: nullableString(item.model),
    sourcePath: nullableString(item.source_path),
    sessionId: nullableString(item.session_id),
    projectPath: nullableString(item.project_path),
    routeSlug: nullableStringOrNull(item.route_slug),
    conversationRef: nullableStringOrNull(item.conversation_ref),
  };
}

export function normalizeConversationRouteResolution(
  value: unknown
): ConversationRouteResolution {
  const item = asRecord(value);
  return {
    conversationRef: stringOr(item.conversation_ref),
    routeSlug: stringOr(item.route_slug),
    projectPath: stringOr(item.project_path),
    sessionId: stringOr(item.session_id),
    threadType: normalizeThreadType(item.thread_type),
    parentSessionId: nullableString(item.parent_session_id),
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
    inputCost: numberOr(field(item, "inputCost", "input_cost")),
    outputCost: numberOr(field(item, "outputCost", "output_cost")),
    cacheWriteCost: numberOr(field(item, "cacheWriteCost", "cache_write_cost")),
    cacheReadCost: numberOr(field(item, "cacheReadCost", "cache_read_cost")),
    longContextPremium: numberOr(field(item, "longContextPremium", "long_context_premium")),
    longContextConversations: numberOr(
      field(item, "longContextConversations", "long_context_conversations")
    ),
    totalCost: numberOr(field(item, "totalCost", "total_cost")),
  };
}

function normalizeProviderBreakdown(value: unknown): ProviderBreakdown {
  const item = asRecord(value);
  return {
    claude: numberOr(field(item, "claude")),
    codex: numberOr(field(item, "codex")),
  };
}

function normalizeRateValue(value: unknown): AnalyticsRateValue {
  const item = asRecord(value);
  return {
    perHour: numberOr(field(item, "perHour", "per_hour")),
    perDay: numberOr(field(item, "perDay", "per_day")),
    perWeek: numberOr(field(item, "perWeek", "per_week")),
    perMonth: numberOr(field(item, "perMonth", "per_month")),
  };
}

function normalizeRates(value: unknown): AnalyticsRates {
  const item = asRecord(value);
  return {
    spend: normalizeRateValue(field(item, "spend")),
    totalTokens: normalizeRateValue(field(item, "totalTokens", "total_tokens", "tokens")),
    inputTokens: normalizeRateValue(field(item, "inputTokens", "input_tokens")),
    outputTokens: normalizeRateValue(field(item, "outputTokens", "output_tokens")),
    cacheWriteTokens: normalizeRateValue(field(item, "cacheWriteTokens", "cache_write_tokens")),
    cacheReadTokens: normalizeRateValue(field(item, "cacheReadTokens", "cache_read_tokens")),
    reasoningTokens: normalizeRateValue(field(item, "reasoningTokens", "reasoning_tokens")),
    conversations: normalizeRateValue(field(item, "conversations")),
    toolCalls: normalizeRateValue(field(item, "toolCalls", "tool_calls")),
    failedToolCalls: normalizeRateValue(field(item, "failedToolCalls", "failed_tool_calls")),
    subagents: normalizeRateValue(field(item, "subagents")),
  };
}

function normalizeTimeSeriesPoint(value: unknown): AnalyticsTimeSeriesPoint {
  const item = asRecord(value);
  return {
    key: stringOr(field(item, "key")),
    label: stringOr(field(item, "label")),
    start: stringOr(field(item, "start")),
    end: stringOr(field(item, "end")),
    estimatedCost: numberOr(field(item, "estimatedCost", "estimated_cost")),
    claudeEstimatedCost: numberOr(
      field(item, "claudeEstimatedCost", "claude_estimated_cost")
    ),
    codexEstimatedCost: numberOr(field(item, "codexEstimatedCost", "codex_estimated_cost")),
    inputTokens: numberOr(field(item, "inputTokens", "input_tokens")),
    outputTokens: numberOr(field(item, "outputTokens", "output_tokens")),
    cacheWriteTokens: numberOr(field(item, "cacheWriteTokens", "cache_write_tokens")),
    cacheReadTokens: numberOr(field(item, "cacheReadTokens", "cache_read_tokens")),
    reasoningTokens: numberOr(field(item, "reasoningTokens", "reasoning_tokens")),
    totalTokens: numberOr(field(item, "totalTokens", "total_tokens")),
    conversations: numberOr(field(item, "conversations")),
    toolCalls: numberOr(field(item, "toolCalls", "tool_calls")),
    failedToolCalls: numberOr(field(item, "failedToolCalls", "failed_tool_calls")),
    toolErrorRatePct: numberOr(field(item, "toolErrorRatePct", "tool_error_rate_pct")),
    subagents: numberOr(field(item, "subagents")),
    claudeInputTokens: numberOr(field(item, "claudeInputTokens", "claude_input_tokens")),
    claudeOutputTokens: numberOr(
      field(item, "claudeOutputTokens", "claude_output_tokens")
    ),
    claudeCacheWriteTokens: numberOr(
      field(item, "claudeCacheWriteTokens", "claude_cache_write_tokens")
    ),
    claudeCacheReadTokens: numberOr(
      field(item, "claudeCacheReadTokens", "claude_cache_read_tokens")
    ),
    claudeReasoningTokens: numberOr(
      field(item, "claudeReasoningTokens", "claude_reasoning_tokens")
    ),
    claudeTotalTokens: numberOr(field(item, "claudeTotalTokens", "claude_total_tokens")),
    claudeConversations: numberOr(
      field(item, "claudeConversations", "claude_conversations")
    ),
    claudeToolCalls: numberOr(field(item, "claudeToolCalls", "claude_tool_calls")),
    claudeFailedToolCalls: numberOr(
      field(item, "claudeFailedToolCalls", "claude_failed_tool_calls")
    ),
    claudeToolErrorRatePct: numberOr(
      field(item, "claudeToolErrorRatePct", "claude_tool_error_rate_pct")
    ),
    claudeSubagents: numberOr(field(item, "claudeSubagents", "claude_subagents")),
    codexInputTokens: numberOr(field(item, "codexInputTokens", "codex_input_tokens")),
    codexOutputTokens: numberOr(field(item, "codexOutputTokens", "codex_output_tokens")),
    codexCacheWriteTokens: numberOr(
      field(item, "codexCacheWriteTokens", "codex_cache_write_tokens")
    ),
    codexCacheReadTokens: numberOr(
      field(item, "codexCacheReadTokens", "codex_cache_read_tokens")
    ),
    codexReasoningTokens: numberOr(
      field(item, "codexReasoningTokens", "codex_reasoning_tokens")
    ),
    codexTotalTokens: numberOr(field(item, "codexTotalTokens", "codex_total_tokens")),
    codexConversations: numberOr(field(item, "codexConversations", "codex_conversations")),
    codexToolCalls: numberOr(field(item, "codexToolCalls", "codex_tool_calls")),
    codexFailedToolCalls: numberOr(
      field(item, "codexFailedToolCalls", "codex_failed_tool_calls")
    ),
    codexToolErrorRatePct: numberOr(
      field(item, "codexToolErrorRatePct", "codex_tool_error_rate_pct")
    ),
    codexSubagents: numberOr(field(item, "codexSubagents", "codex_subagents")),
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
    date: stringOr(field(item, "date")),
    inputTokens: numberOr(field(item, "inputTokens", "input_tokens")),
    outputTokens: numberOr(field(item, "outputTokens", "output_tokens")),
    cacheWriteTokens: numberOr(field(item, "cacheWriteTokens", "cache_write_tokens")),
    cacheReadTokens: numberOr(field(item, "cacheReadTokens", "cache_read_tokens")),
    conversations: numberOr(field(item, "conversations")),
    subagents: numberOr(field(item, "subagents")),
    claudeInputTokens: numberOr(field(item, "claudeInputTokens", "claude_input_tokens")),
    claudeOutputTokens: numberOr(
      field(item, "claudeOutputTokens", "claude_output_tokens")
    ),
    claudeCacheWriteTokens: numberOr(
      field(item, "claudeCacheWriteTokens", "claude_cache_write_tokens")
    ),
    claudeCacheReadTokens: numberOr(
      field(item, "claudeCacheReadTokens", "claude_cache_read_tokens")
    ),
    codexInputTokens: numberOr(field(item, "codexInputTokens", "codex_input_tokens")),
    codexOutputTokens: numberOr(field(item, "codexOutputTokens", "codex_output_tokens")),
    codexCacheWriteTokens: numberOr(
      field(item, "codexCacheWriteTokens", "codex_cache_write_tokens")
    ),
    codexCacheReadTokens: numberOr(
      field(item, "codexCacheReadTokens", "codex_cache_read_tokens")
    ),
    claudeConversations: numberOr(
      field(item, "claudeConversations", "claude_conversations")
    ),
    codexConversations: numberOr(field(item, "codexConversations", "codex_conversations")),
    claudeSubagents: numberOr(field(item, "claudeSubagents", "claude_subagents")),
    codexSubagents: numberOr(field(item, "codexSubagents", "codex_subagents")),
  };
}

export function normalizeAnalytics(value: unknown): AnalyticsData {
  const item = asRecord(value);
  const modelBreakdownByProvider = asRecord(
    field(item, "modelBreakdownByProvider", "model_breakdown_by_provider")
  );
  const toolBreakdownByProvider = asRecord(
    field(item, "toolBreakdownByProvider", "tool_breakdown_by_provider")
  );
  const subagentTypeBreakdownByProvider = asRecord(
    field(item, "subagentTypeBreakdownByProvider", "subagent_type_breakdown_by_provider")
  );
  const costBreakdownByProvider = asRecord(
    field(item, "costBreakdownByProvider", "cost_breakdown_by_provider")
  );
  const costBreakdownByModel = asRecord(
    field(item, "costBreakdownByModel", "cost_breakdown_by_model")
  );

  return {
    totalConversations: numberOr(field(item, "totalConversations", "total_conversations")),
    totalInputTokens: numberOr(field(item, "totalInputTokens", "total_input_tokens")),
    totalOutputTokens: numberOr(field(item, "totalOutputTokens", "total_output_tokens")),
    totalCacheCreationTokens: numberOr(
      field(item, "totalCacheCreationTokens", "total_cache_creation_tokens")
    ),
    totalCacheReadTokens: numberOr(field(item, "totalCacheReadTokens", "total_cache_read_tokens")),
    totalReasoningTokens: numberOr(
      field(item, "totalReasoningTokens", "total_reasoning_tokens")
    ),
    totalToolCalls: numberOr(field(item, "totalToolCalls", "total_tool_calls")),
    totalFailedToolCalls: numberOr(
      field(item, "totalFailedToolCalls", "total_failed_tool_calls")
    ),
    modelBreakdown: asRecord(field(item, "modelBreakdown", "model_breakdown")) as Record<
      string,
      number
    >,
    toolBreakdown: asRecord(field(item, "toolBreakdown", "tool_breakdown")) as Record<
      string,
      number
    >,
    subagentTypeBreakdown: asRecord(
      field(item, "subagentTypeBreakdown", "subagent_type_breakdown")
    ) as Record<string, number>,
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
    dailyUsage: asArray(field(item, "dailyUsage", "daily_usage")).map(normalizeDailyUsage),
    rates: normalizeRates(field(item, "rates")),
    timeSeries: normalizeTimeSeries(field(item, "timeSeries", "time_series")),
    estimatedCost: numberOr(field(item, "estimatedCost", "estimated_cost")),
    costBreakdown: normalizeCostBreakdown(field(item, "costBreakdown", "cost_breakdown")),
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
    sizeBytes:
      field(item, "sizeBytes", "size_bytes") === null
        ? null
        : nullableNumber(field(item, "sizeBytes", "size_bytes")),
    sizeDisplay:
      field(item, "sizeDisplay", "size_display") === null
        ? null
        : nullableString(field(item, "sizeDisplay", "size_display")),
    columns: asArray(field(item, "columns")).map(normalizeDatabaseColumn),
  };
}

function normalizeDatabaseLoadMetric(value: unknown): DatabaseLoadMetric {
  const item = asRecord(value);
  return {
    label: stringOr(field(item, "label")),
    value:
      field(item, "value") === null ? null : nullableNumber(field(item, "value")),
    displayValue:
      field(item, "displayValue", "display_value") === null
        ? null
        : nullableString(field(item, "displayValue", "display_value")),
  };
}

function normalizeDatabaseArtifact(
  value: DatabaseArtifactPayload | undefined
): DatabaseArtifactStatus {
  if (!value) {
    return {
      key: "" as DatabaseArtifactStatus["key"],
      label: "",
      engine: "",
      role: "" as DatabaseArtifactStatus["role"],
      availability: "" as DatabaseArtifactStatus["availability"],
      tableCount: 0,
      load: [],
      tables: [],
    };
  }

  const key = value.key;
  const role = value.role;
  let operationalStatus: string | null | undefined;
  let tableCount: number;
  let sizeBytes: number | null | undefined;
  let sizeDisplay: string | null | undefined;
  let inventorySummary: string | null | undefined;

  if ("table_count" in value) {
    const snakeCaseValue = value as SnakeDatabaseArtifactPayload;
    operationalStatus = snakeCaseValue.operational_status;
    tableCount = snakeCaseValue.table_count;
    sizeBytes = snakeCaseValue.size_bytes;
    sizeDisplay = snakeCaseValue.size_display;
    inventorySummary = snakeCaseValue.inventory_summary;
  } else {
    const camelCaseValue = value as CamelDatabaseArtifactPayload;
    operationalStatus = camelCaseValue.operationalStatus;
    tableCount = camelCaseValue.tableCount;
    sizeBytes = camelCaseValue.sizeBytes;
    sizeDisplay = camelCaseValue.sizeDisplay;
    inventorySummary = camelCaseValue.inventorySummary;
  }

  return {
    key: key as DatabaseArtifactStatus["key"],
    label: value.label,
    engine: value.engine,
    role: role as DatabaseArtifactStatus["role"],
    availability: value.availability as DatabaseArtifactStatus["availability"],
    health: value.health ?? null,
    operationalStatus: operationalStatus ?? null,
    note: value.note ?? null,
    error: value.error ?? null,
    path: value.path ?? null,
    target: value.target ?? null,
    tableCount,
    sizeBytes: sizeBytes ?? null,
    sizeDisplay: sizeDisplay ?? null,
    inventorySummary: inventorySummary ?? null,
    load: value.load.map(normalizeDatabaseLoadMetric),
    tables: value.tables.map(normalizeDatabaseTable),
  };
}

export function normalizeDatabaseStatus(value: DatabaseStatusPayload): DatabaseStatus {
  const startedAt = value.startedAt ?? value.started_at ?? null;
  const finishedAt = value.finishedAt ?? value.finished_at ?? null;
  const durationMs = value.durationMs ?? value.duration_ms ?? null;
  const lastSuccessfulRefreshAt =
    value.lastSuccessfulRefreshAt ?? value.last_successful_refresh_at ?? null;
  const idempotencyKey = value.idempotencyKey ?? value.idempotency_key ?? null;
  const scopeLabel = value.scopeLabel ?? value.scope_label ?? "";
  const windowDays = value.windowDays ?? value.window_days ?? 0;
  const windowStart = value.windowStart ?? value.window_start ?? null;
  const windowEnd = value.windowEnd ?? value.window_end ?? null;
  const sourceConversationCount =
    value.sourceConversationCount ?? value.source_conversation_count ?? 0;
  const refreshIntervalMinutes =
    value.refreshIntervalMinutes ?? value.refresh_interval_minutes ?? 360;
  const analyticsReadBackend =
    "analytics_read_backend" in value.runtime
      ? value.runtime.analytics_read_backend
      : value.runtime.analyticsReadBackend;
  const conversationSummaryReadBackend =
    "conversation_summary_read_backend" in value.runtime
      ? value.runtime.conversation_summary_read_backend
      : value.runtime.conversationSummaryReadBackend;

  return {
    status: value.status,
    trigger: value.trigger,
    startedAt,
    finishedAt,
    durationMs,
    error: value.error ?? null,
    lastSuccessfulRefreshAt,
    idempotencyKey,
    scopeLabel,
    windowDays,
    windowStart,
    windowEnd,
    sourceConversationCount,
    refreshIntervalMinutes,
    runtime: {
      analyticsReadBackend:
        analyticsReadBackend as DatabaseStatus["runtime"]["analyticsReadBackend"],
      conversationSummaryReadBackend:
        conversationSummaryReadBackend as DatabaseStatus["runtime"]["conversationSummaryReadBackend"],
    },
    databases: {
      frontendCache: normalizeDatabaseArtifact(
        value.databases.frontend_cache ?? value.databases.frontendCache
      ),
      sqlite: normalizeDatabaseArtifact(value.databases.sqlite),
      duckdb: normalizeDatabaseArtifact(
        value.databases.duckdb ?? value.databases.legacy_duckdb ?? value.databases.legacyDuckdb
      ),
      prefectPostgres: normalizeDatabaseArtifact(
        value.databases.prefect_postgres ?? value.databases.prefectPostgres
      ),
    },
  };
}

export function normalizeEvaluationPrompt(value: EvaluationPromptPayload): EvaluationPrompt {
  const promptId = "promptId" in value ? value.promptId : value.prompt_id;
  const promptText = "promptText" in value ? value.promptText : value.prompt_text;
  const isDefault = "isDefault" in value ? value.isDefault : value.is_default;
  const createdAt = "createdAt" in value ? value.createdAt : value.created_at;
  const updatedAt = "updatedAt" in value ? value.updatedAt : value.updated_at;

  return {
    promptId,
    name: value.name,
    description: value.description ?? null,
    promptText,
    isDefault,
    createdAt,
    updatedAt,
  };
}

export function normalizeEvaluationPrompts(value: EvaluationPromptPayload[]): EvaluationPrompt[] {
  return value.map(normalizeEvaluationPrompt);
}

export function normalizeConversationEvaluation(
  value: ConversationEvaluationPayload
): ConversationEvaluation {
  const evaluationId = "evaluationId" in value ? value.evaluationId : value.evaluation_id;
  const conversationId = "conversationId" in value ? value.conversationId : value.conversation_id;
  const promptId = "promptId" in value ? value.promptId : value.prompt_id;
  const selectionInstruction =
    "selectionInstruction" in value ? value.selectionInstruction : value.selection_instruction;
  const promptName = "promptName" in value ? value.promptName : value.prompt_name;
  const promptText = "promptText" in value ? value.promptText : value.prompt_text;
  const reportMarkdown =
    "reportMarkdown" in value ? value.reportMarkdown : value.report_markdown;
  const rawOutput = "rawOutput" in value ? value.rawOutput : value.raw_output;
  const errorMessage = "errorMessage" in value ? value.errorMessage : value.error_message;
  const createdAt = "createdAt" in value ? value.createdAt : value.created_at;
  const finishedAt = "finishedAt" in value ? value.finishedAt : value.finished_at;
  const durationMs = "durationMs" in value ? value.durationMs : value.duration_ms;

  return {
    evaluationId,
    conversationId,
    promptId: promptId ?? null,
    provider: value.provider,
    model: value.model,
    status: value.status,
    scope: value.scope,
    selectionInstruction: selectionInstruction ?? null,
    promptName,
    promptText,
    reportMarkdown: reportMarkdown ?? null,
    rawOutput: rawOutput ?? null,
    errorMessage: errorMessage ?? null,
    command: value.command,
    createdAt,
    finishedAt: finishedAt ?? null,
    durationMs: durationMs ?? null,
  };
}

export function normalizeConversationEvaluations(
  value: ConversationEvaluationPayload[]
): ConversationEvaluation[] {
  return value.map(normalizeConversationEvaluation);
}

function normalizeProviderSubscription(
  value: SubscriptionSettingsPayload["claude"]
): SubscriptionSettings["claude"] {
  const hasSubscription =
    "hasSubscription" in value ? value.hasSubscription : value.has_subscription;
  const monthlyCost = "monthlyCost" in value ? value.monthlyCost : value.monthly_cost;
  const updatedAt = "updatedAt" in value ? value.updatedAt : value.updated_at;

  return {
    provider: value.provider,
    hasSubscription,
    monthlyCost,
    updatedAt,
  };
}

export function normalizeSubscriptionSettings(
  value: SubscriptionSettingsPayload
): SubscriptionSettings {
  return {
    claude: normalizeProviderSubscription(value.claude),
    codex: normalizeProviderSubscription(value.codex),
  };
}

function normalizePrefectOatsMetadata(value: unknown): PrefectOatsMetadata | undefined {
  const item = asRecord(value);
  if (Object.keys(item).length === 0) {
    return undefined;
  }

  const repoRoot = nullableString(field(item, "repoRoot", "repo_root"));
  const sourcePath = nullableString(field(item, "sourcePath", "source_path"));
  const configPath = nullableString(field(item, "configPath", "config_path"));
  const localMetadataPath = nullableString(field(item, "localMetadataPath", "local_metadata_path"));
  const artifactRoot = nullableString(field(item, "artifactRoot", "artifact_root"));

  const metadata: PrefectOatsMetadata = {
    runTitle: nullableString(field(item, "runTitle", "run_title")),
    sourcePath,
    repoRoot,
    configPath,
    localMetadataPath,
    artifactRoot,
    repoLabel: basename(repoRoot),
    sourceLabel: basename(sourcePath),
    sourceHref: toRepoHref(sourcePath, repoRoot),
    configHref: toRepoHref(configPath, repoRoot),
    metadataHref: toRepoHref(localMetadataPath, repoRoot),
    artifactHref: toRepoHref(artifactRoot, repoRoot),
  };

  return Object.fromEntries(
    Object.entries(metadata).filter(([, entry]) => entry !== undefined)
  ) as PrefectOatsMetadata;
}

function normalizeBooleanLike(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function normalizeInvocation(value: unknown): OrchestrationInvocation | null {
  if (value === null) {
    return null;
  }

  const item = asRecord(value);
  return {
    agent: stringOr(field(item, "agent")),
    role: stringOr(field(item, "role")),
    command: asArray(field(item, "command")).map((entry) => stringOr(entry)),
    cwd: stringOr(field(item, "cwd")),
    prompt: stringOr(field(item, "prompt")),
    sessionId: nullableString(field(item, "sessionId", "session_id")),
    sessionIdField: nullableString(field(item, "sessionIdField", "session_id_field")),
    requestedSessionId: nullableString(field(item, "requestedSessionId", "requested_session_id")),
    outputText: stringOr(field(item, "outputText", "output_text")),
    rawStdout: stringOr(field(item, "rawStdout", "raw_stdout")),
    rawStderr: stringOr(field(item, "rawStderr", "raw_stderr")),
    exitCode: nullableNumber(field(item, "exitCode", "exit_code")),
    timedOut: booleanOr(field(item, "timedOut", "timed_out")),
    startedAt: stringOr(field(item, "startedAt", "started_at")),
    finishedAt: nullableString(field(item, "finishedAt", "finished_at")),
    projectPath: nullableString(field(item, "projectPath", "project_path")),
    conversationPath: nullableString(field(item, "conversationPath", "conversation_path")),
  };
}

function normalizeLooseRecord(value: unknown): Record<string, unknown> {
  return Object.fromEntries(Object.entries(asRecord(value)));
}

function normalizeReviewSummary(value: unknown): OrchestrationReviewSummary | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }

  const item = asRecord(value);
  return {
    blockingState: stringOr(
      field(item, "blockingState", "blocking_state"),
      "unknown"
    ) as OrchestrationReviewSummary["blockingState"],
    approvals: numberOr(field(item, "approvals")),
    changesRequested: numberOr(field(item, "changesRequested", "changes_requested")),
  };
}

function normalizeFeatureBranch(value: unknown): OrchestrationFeatureBranch | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }

  const item = asRecord(value);
  return {
    name: stringOr(field(item, "name")),
    baseBranch:
      field(item, "baseBranch", "base_branch") === null
        ? null
        : nullableString(field(item, "baseBranch", "base_branch")),
  };
}

function normalizeTaskPullRequest(value: unknown): OrchestrationTaskPullRequest | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }

  const item = asRecord(value);
  return {
    number:
      field(item, "number") === null ? null : nullableNumber(field(item, "number")),
    url: field(item, "url") === null ? null : nullableString(field(item, "url")),
    state: stringOr(field(item, "state")) as OrchestrationTaskPullRequest["state"],
    mergeGateStatus: stringOr(
      field(item, "mergeGateStatus", "merge_gate_status")
    ) as OrchestrationTaskPullRequest["mergeGateStatus"],
    baseBranch:
      field(item, "baseBranch", "base_branch") === null
        ? null
        : nullableString(field(item, "baseBranch", "base_branch")),
    headBranch:
      field(item, "headBranch", "head_branch") === null
        ? null
        : nullableString(field(item, "headBranch", "head_branch")),
    mergeability:
      field(item, "mergeability") === null
        ? null
        : nullableString(field(item, "mergeability")),
    checksSummary: normalizeLooseRecord(field(item, "checksSummary", "checks_summary")),
    reviewSummary: normalizeReviewSummary(field(item, "reviewSummary", "review_summary")),
    snapshotSource:
      field(item, "snapshotSource", "snapshot_source") === null
        ? null
        : nullableString(field(item, "snapshotSource", "snapshot_source")),
    lastRefreshedAt:
      field(item, "lastRefreshedAt", "last_refreshed_at") === null
        ? null
        : nullableString(field(item, "lastRefreshedAt", "last_refreshed_at")),
    isStale: booleanOr(field(item, "isStale", "is_stale")),
  };
}

function normalizeFinalPullRequest(value: unknown): OrchestrationFinalPullRequest | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }

  const item = asRecord(value);
  return {
    number:
      field(item, "number") === null ? null : nullableNumber(field(item, "number")),
    url: field(item, "url") === null ? null : nullableString(field(item, "url")),
    state: stringOr(field(item, "state")) as OrchestrationFinalPullRequest["state"],
    reviewGateStatus: stringOr(
      field(item, "reviewGateStatus", "review_gate_status")
    ) as OrchestrationFinalPullRequest["reviewGateStatus"],
    baseBranch:
      field(item, "baseBranch", "base_branch") === null
        ? null
        : nullableString(field(item, "baseBranch", "base_branch")),
    headBranch:
      field(item, "headBranch", "head_branch") === null
        ? null
        : nullableString(field(item, "headBranch", "head_branch")),
    checksSummary: normalizeLooseRecord(field(item, "checksSummary", "checks_summary")),
    snapshotSource:
      field(item, "snapshotSource", "snapshot_source") === null
        ? null
        : nullableString(field(item, "snapshotSource", "snapshot_source")),
    lastRefreshedAt:
      field(item, "lastRefreshedAt", "last_refreshed_at") === null
        ? null
        : nullableString(field(item, "lastRefreshedAt", "last_refreshed_at")),
    isStale: booleanOr(field(item, "isStale", "is_stale")),
  };
}

function normalizeOperationHistoryEntry(value: unknown): OrchestrationOperationHistoryEntry {
  const item = asRecord(value);
  return {
    kind: stringOr(field(item, "kind")),
    status: stringOr(field(item, "status")) as OrchestrationOperationHistoryEntry["status"],
    sessionId:
      field(item, "sessionId", "session_id") === null
        ? null
        : nullableString(field(item, "sessionId", "session_id")),
    startedAt: stringOr(field(item, "startedAt", "started_at")),
    finishedAt:
      field(item, "finishedAt", "finished_at") === null
        ? null
        : nullableString(field(item, "finishedAt", "finished_at")),
    details: normalizeLooseRecord(field(item, "details")),
  };
}

function normalizeOrchestrationTask(value: unknown): OrchestrationTaskRecord {
  const item = asRecord(value);
  return {
    taskId: stringOr(field(item, "taskId", "task_id")),
    title: stringOr(field(item, "title")),
    dependsOn: asArray(field(item, "dependsOn", "depends_on")).map((entry) => stringOr(entry)),
    parentBranch:
      field(item, "parentBranch", "parent_branch") === null
        ? null
        : nullableString(field(item, "parentBranch", "parent_branch")),
    status: stringOr(field(item, "status")) as OrchestrationTaskRecord["status"],
    attempts: numberOr(field(item, "attempts")),
    taskPr: normalizeTaskPullRequest(field(item, "taskPr", "task_pr")),
    operationHistory: asArray(field(item, "operationHistory", "operation_history")).map(
      normalizeOperationHistoryEntry
    ),
    invocation:
      field(item, "invocation") === undefined ? null : normalizeInvocation(field(item, "invocation")),
  };
}

function normalizeOrchestrationDag(value: unknown): OrchestrationDag {
  const item = asRecord(value);
  const stats = asRecord(field(item, "stats"));

  return {
    nodes: asArray(field(item, "nodes")).map((entry) => {
      const node = asRecord(entry);
      return {
        id: stringOr(field(node, "id")),
        kind: stringOr(field(node, "kind")) as OrchestrationDagNode["kind"],
        label: stringOr(field(node, "label")),
        description: nullableString(field(node, "description")),
        role: stringOr(field(node, "role")),
        agent: stringOr(field(node, "agent")),
        sessionId: nullableString(field(node, "sessionId", "session_id")),
        projectPath: nullableString(field(node, "projectPath", "project_path")),
        conversationPath: nullableString(field(node, "conversationPath", "conversation_path")),
        status: stringOr(field(node, "status")) as OrchestrationDagNode["status"],
        isActive: booleanOr(field(node, "isActive", "is_active")),
        isStale: booleanOr(field(node, "isStale", "is_stale")),
        statusTone: nullableString(field(node, "statusTone", "status_tone")) as
          | OrchestrationDagNode["statusTone"]
          | undefined,
        statusLabel: nullableString(field(node, "statusLabel", "status_label")),
        attempts: nullableNumber(field(node, "attempts")),
        lastHeartbeatAt: nullableString(field(node, "lastHeartbeatAt", "last_heartbeat_at")),
        exitCode: nullableNumber(field(node, "exitCode", "exit_code")),
        timedOut: booleanOr(field(node, "timedOut", "timed_out")),
        depth: numberOr(field(node, "depth")),
      };
    }),
    edges: asArray(field(item, "edges")).map((entry) => {
      const edge = asRecord(entry);
      return {
        id: stringOr(field(edge, "id")),
        source: stringOr(field(edge, "source")),
        target: stringOr(field(edge, "target")),
        label: nullableString(field(edge, "label")),
      };
    }),
    stats: {
      totalNodes: numberOr(field(stats, "totalNodes", "total_nodes")),
      totalEdges: numberOr(field(stats, "totalEdges", "total_edges")),
      maxDepth: numberOr(field(stats, "maxDepth", "max_depth")),
      maxBreadth: numberOr(field(stats, "maxBreadth", "max_breadth")),
      rootCount: numberOr(field(stats, "rootCount", "root_count")),
      providerBreakdown: asRecord(
        field(stats, "providerBreakdown", "provider_breakdown")
      ) as Record<string, number>,
      timedOutCount: numberOr(field(stats, "timedOutCount", "timed_out_count")),
      activeCount: numberOr(field(stats, "activeCount", "active_count")),
      pendingCount: numberOr(field(stats, "pendingCount", "pending_count")),
      failedCount: numberOr(field(stats, "failedCount", "failed_count")),
      succeededCount: numberOr(field(stats, "succeededCount", "succeeded_count")),
    },
  };
}

function normalizeOrchestrationEvaluation(value: unknown): OrchestrationRunEvaluation | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }

  const item = asRecord(value);
  const summary = asRecord(field(item, "summary"));

  return {
    summary: {
      conversationCount: numberOr(field(summary, "conversationCount", "conversation_count")),
      linkedConversationCount: numberOr(
        field(summary, "linkedConversationCount", "linked_conversation_count")
      ),
      missingConversationCount: numberOr(
        field(summary, "missingConversationCount", "missing_conversation_count")
      ),
      activeConversationCount: numberOr(
        field(summary, "activeConversationCount", "active_conversation_count")
      ),
      failedConversationCount: numberOr(
        field(summary, "failedConversationCount", "failed_conversation_count")
      ),
      providerBreakdown: asRecord(
        field(summary, "providerBreakdown", "provider_breakdown")
      ) as Record<string, number>,
    },
    conversations: asArray(field(item, "conversations")).map((entry) => {
      const conversation = asRecord(entry);
      return {
        nodeId: stringOr(field(conversation, "nodeId", "node_id")),
        label: stringOr(field(conversation, "label")),
        role: stringOr(field(conversation, "role")),
        agent: stringOr(field(conversation, "agent")),
        status: stringOr(field(conversation, "status")) as OrchestrationRunEvaluationConversation["status"],
        taskId: nullableString(field(conversation, "taskId", "task_id")),
        sessionId: nullableString(field(conversation, "sessionId", "session_id")),
        projectPath: nullableString(field(conversation, "projectPath", "project_path")),
        conversationPath: nullableString(
          field(conversation, "conversationPath", "conversation_path")
        ),
        startedAt: stringOr(field(conversation, "startedAt", "started_at")),
        finishedAt: nullableString(field(conversation, "finishedAt", "finished_at")),
        hasSessionLink:
          normalizeBooleanLike(field(conversation, "hasSessionLink", "has_session_link")) ??
          Boolean(field(conversation, "conversationPath", "conversation_path")),
      };
    }),
  };
}

export function normalizeOvernightOatsRun(value: unknown): OvernightOatsRunRecord {
  const item = asRecord(value);
  const contractVersion = stringOr(field(item, "contractVersion", "contract_version"));
  return {
    source:
      stringOr(field(item, "source")) === "overnight-oats" ? "overnight-oats" : "overnight-oats",
    contractVersion:
      contractVersion === "oats-run-v1" ||
      contractVersion === "oats-run-v2" ||
      contractVersion === "oats-runtime-v1" ||
      contractVersion === "oats-runtime-v2"
        ? contractVersion
        : "oats-runtime-v1",
    runId: stringOr(field(item, "runId", "run_id")),
    runTitle: stringOr(field(item, "runTitle", "run_title")),
    repoRoot: stringOr(field(item, "repoRoot", "repo_root")),
    configPath: stringOr(field(item, "configPath", "config_path")),
    runSpecPath: stringOr(field(item, "runSpecPath", "run_spec_path")),
    mode: stringOr(field(item, "mode")),
    integrationBranch: stringOr(field(item, "integrationBranch", "integration_branch")),
    taskPrTarget: stringOr(field(item, "taskPrTarget", "task_pr_target")),
    finalPrTarget: stringOr(field(item, "finalPrTarget", "final_pr_target")),
    status: stringOr(field(item, "status")) as OvernightOatsRunRecord["status"],
    stackStatus:
      field(item, "stackStatus", "stack_status") === null
        ? null
        : (nullableString(field(item, "stackStatus", "stack_status")) as
            | OvernightOatsRunRecord["stackStatus"]
            | undefined),
    featureBranch: normalizeFeatureBranch(field(item, "featureBranch", "feature_branch")),
    activeTaskId:
      field(item, "activeTaskId", "active_task_id") === null
        ? null
        : nullableString(field(item, "activeTaskId", "active_task_id")),
    heartbeatAt:
      field(item, "heartbeatAt", "heartbeat_at") === null
        ? null
        : nullableString(field(item, "heartbeatAt", "heartbeat_at")),
    finishedAt:
      field(item, "finishedAt", "finished_at") === null
        ? null
        : nullableString(field(item, "finishedAt", "finished_at")),
    planner:
      field(item, "planner") === undefined ? null : normalizeInvocation(field(item, "planner")),
    tasks: asArray(field(item, "tasks")).map(normalizeOrchestrationTask),
    finalPr: normalizeFinalPullRequest(field(item, "finalPr", "final_pr")),
    operationHistory: asArray(field(item, "operationHistory", "operation_history")).map(
      normalizeOperationHistoryEntry
    ),
    createdAt: stringOr(field(item, "createdAt", "created_at")),
    lastUpdatedAt: stringOr(field(item, "lastUpdatedAt", "last_updated_at")),
    isRunning:
      normalizeBooleanLike(field(item, "isRunning", "is_running")) ??
      stringOr(field(item, "status")) === "running",
    recordedAt: stringOr(field(item, "recordedAt", "recorded_at")),
    recordPath: stringOr(field(item, "recordPath", "record_path")),
    dag: normalizeOrchestrationDag(field(item, "dag")),
    evaluation: normalizeOrchestrationEvaluation(field(item, "evaluation")),
  };
}

export function normalizeOvernightOatsRuns(value: unknown): OvernightOatsRunRecord[] {
  return asArray(value).map(normalizeOvernightOatsRun);
}

export function normalizePrefectDeployments(value: unknown): PrefectDeploymentRecord[] {
  return asArray(value).map((entry) => {
    const item = asRecord(entry);
    return {
      deploymentId: stringOr(field(item, "deploymentId", "deployment_id")),
      deploymentName: stringOr(field(item, "deploymentName", "deployment_name")),
      flowId: nullableString(field(item, "flowId", "flow_id")),
      flowName: nullableString(field(item, "flowName", "flow_name")),
      workPoolName: nullableString(field(item, "workPoolName", "work_pool_name")),
      workQueueName: nullableString(field(item, "workQueueName", "work_queue_name")),
      status: nullableString(field(item, "status")),
      updatedAt: nullableString(field(item, "updatedAt", "updated_at")),
      tags: asArray(field(item, "tags")).map((tag) => stringOr(tag)).filter(Boolean),
      oatsMetadata: normalizePrefectOatsMetadata(field(item, "oatsMetadata", "oats_metadata")),
    };
  });
}

export function normalizePrefectFlowRuns(value: unknown): PrefectFlowRunRecord[] {
  return asArray(value).map((entry) => {
    const item = asRecord(entry);
    const stateName = nullableString(field(item, "stateName", "state_name"));
    const stateType = nullableString(field(item, "stateType", "state_type"));
    const backendStatusTone = nullableString(field(item, "statusTone", "status_tone"));
    const backendStatusLabel = nullableString(field(item, "statusLabel", "status_label"));
    const backendIsActive = normalizeBooleanLike(field(item, "isActive", "is_active"));
    return {
      flowRunId: stringOr(field(item, "flowRunId", "flow_run_id")),
      flowRunName: nullableString(field(item, "flowRunName", "flow_run_name")),
      deploymentId: nullableString(field(item, "deploymentId", "deployment_id")),
      deploymentName: nullableString(field(item, "deploymentName", "deployment_name")),
      flowId: nullableString(field(item, "flowId", "flow_id")),
      flowName: nullableString(field(item, "flowName", "flow_name")),
      workPoolName: nullableString(field(item, "workPoolName", "work_pool_name")),
      workQueueName: nullableString(field(item, "workQueueName", "work_queue_name")),
      stateType,
      stateName,
      createdAt: nullableString(field(item, "createdAt", "created_at")),
      updatedAt: nullableString(field(item, "updatedAt", "updated_at")),
      oatsMetadata: normalizePrefectOatsMetadata(field(item, "oatsMetadata", "oats_metadata")),
      statusTone:
        (backendStatusTone as PrefectFlowRunRecord["statusTone"] | undefined) ??
        normalizePrefectRunTone(stateType),
      statusLabel: backendStatusLabel ?? stateName ?? stateType ?? "Unknown",
      isActive: backendIsActive ?? (stateType === "RUNNING" || stateType === "PENDING"),
    };
  });
}

export function normalizePrefectWorkers(value: unknown): PrefectWorkerRecord[] {
  return asArray(value).map((entry) => {
    const item = asRecord(entry);
    const status = nullableString(field(item, "status"));
    const backendStatusTone = nullableString(field(item, "statusTone", "status_tone"));
    const backendIsOnline = normalizeBooleanLike(field(item, "isOnline", "is_online"));
    return {
      workerId: stringOr(field(item, "workerId", "worker_id")),
      workerName: stringOr(field(item, "workerName", "worker_name")),
      workPoolName: nullableString(field(item, "workPoolName", "work_pool_name")),
      status,
      lastHeartbeatAt: nullableString(field(item, "lastHeartbeatAt", "last_heartbeat_at")),
      statusTone:
        (backendStatusTone as PrefectWorkerRecord["statusTone"] | undefined) ??
        normalizeInfraTone(status),
      isOnline: backendIsOnline ?? status?.toUpperCase() === "ONLINE",
    };
  });
}

export function normalizePrefectWorkPools(
  value: unknown,
  workers: PrefectWorkerRecord[] = []
): PrefectWorkPoolRecord[] {
  return asArray(value).map((entry) => {
    const item = asRecord(entry);
    const workPoolName = stringOr(field(item, "workPoolName", "work_pool_name"));
    const attachedWorkers = workers.filter((worker) => worker.workPoolName === workPoolName);
    const status = nullableString(field(item, "status"));
    const isPaused = booleanOr(field(item, "isPaused", "is_paused"));
    const backendWorkerCount = nullableNumber(field(item, "workerCount", "worker_count"));
    const backendOnlineWorkerCount = nullableNumber(
      field(item, "onlineWorkerCount", "online_worker_count")
    );
    const backendStatusTone = nullableString(field(item, "statusTone", "status_tone"));
    return {
      workPoolId: stringOr(field(item, "workPoolId", "work_pool_id")),
      workPoolName,
      type: nullableString(field(item, "type")),
      status,
      isPaused,
      concurrencyLimit:
        field(item, "concurrencyLimit", "concurrency_limit") === null
          ? undefined
          : (nullableString(field(item, "concurrencyLimit", "concurrency_limit")) !== undefined ||
            typeof field(item, "concurrencyLimit", "concurrency_limit") === "number")
          ? numberOr(field(item, "concurrencyLimit", "concurrency_limit"))
          : undefined,
      workerCount: backendWorkerCount ?? attachedWorkers.length,
      onlineWorkerCount:
        backendOnlineWorkerCount ?? attachedWorkers.filter((worker) => worker.isOnline).length,
      statusTone:
        (backendStatusTone as PrefectWorkPoolRecord["statusTone"] | undefined) ??
        (isPaused ? "warning" : normalizeInfraTone(status)),
    };
  });
}

export function normalizeTasks(value: unknown): unknown[] {
  const item = asRecord(value);
  return asArray(item.tasks);
}
