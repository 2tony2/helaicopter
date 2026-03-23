import { z } from "zod";

import { nonEmptyTrimmedString, providerSchema } from "./shared.ts";

const threadTypeSchema = z.enum(["main", "subagent"]);
const nullableTrimmedString = z.union([z.string().trim(), z.null()]);
const countMapSchema = z.record(z.string(), z.number().int().nonnegative());
const jsonValueSchema: z.ZodType<unknown> = z.lazy(() =>
  z.union([z.string(), z.number(), z.boolean(), z.null(), z.array(jsonValueSchema), z.record(z.string(), jsonValueSchema)])
);
const jsonObjectSchema = z.record(z.string(), jsonValueSchema);

const conversationSummarySnakeSchema = z.object({
  session_id: nonEmptyTrimmedString,
  project_path: nonEmptyTrimmedString,
  project_name: nonEmptyTrimmedString,
  route_slug: nonEmptyTrimmedString,
  conversation_ref: nonEmptyTrimmedString,
  thread_type: threadTypeSchema,
  first_message: nonEmptyTrimmedString,
  timestamp: z.number().finite(),
  created_at: z.number().finite(),
  last_updated_at: z.number().finite(),
  is_running: z.boolean(),
  message_count: z.number().int().nonnegative(),
  model: nullableTrimmedString,
  total_input_tokens: z.number().int().nonnegative(),
  total_output_tokens: z.number().int().nonnegative(),
  total_cache_creation_tokens: z.number().int().nonnegative(),
  total_cache_read_tokens: z.number().int().nonnegative(),
  tool_use_count: z.number().int().nonnegative(),
  failed_tool_call_count: z.number().int().nonnegative(),
  tool_breakdown: countMapSchema,
  subagent_count: z.number().int().nonnegative(),
  subagent_type_breakdown: countMapSchema,
  task_count: z.number().int().nonnegative(),
  git_branch: nullableTrimmedString,
  reasoning_effort: nullableTrimmedString,
  speed: nullableTrimmedString,
  total_reasoning_tokens: z.union([z.number().int().nonnegative(), z.null()]).optional(),
});

const conversationSummaryCamelSchema = z.object({
  sessionId: nonEmptyTrimmedString,
  projectPath: nonEmptyTrimmedString,
  projectName: nonEmptyTrimmedString,
  routeSlug: nonEmptyTrimmedString,
  conversationRef: nonEmptyTrimmedString,
  threadType: threadTypeSchema,
  firstMessage: nonEmptyTrimmedString,
  timestamp: z.number().finite(),
  createdAt: z.number().finite(),
  lastUpdatedAt: z.number().finite(),
  isRunning: z.boolean(),
  messageCount: z.number().int().nonnegative(),
  model: nullableTrimmedString,
  totalInputTokens: z.number().int().nonnegative(),
  totalOutputTokens: z.number().int().nonnegative(),
  totalCacheCreationTokens: z.number().int().nonnegative(),
  totalCacheReadTokens: z.number().int().nonnegative(),
  toolUseCount: z.number().int().nonnegative(),
  failedToolCallCount: z.number().int().nonnegative(),
  toolBreakdown: countMapSchema,
  subagentCount: z.number().int().nonnegative(),
  subagentTypeBreakdown: countMapSchema,
  taskCount: z.number().int().nonnegative(),
  gitBranch: nullableTrimmedString,
  reasoningEffort: nullableTrimmedString,
  speed: nullableTrimmedString,
  totalReasoningTokens: z.union([z.number().int().nonnegative(), z.null()]).optional(),
});

export const conversationSummarySchema = z.union([
  conversationSummarySnakeSchema,
  conversationSummaryCamelSchema,
]);

export const conversationSummaryListSchema = z.array(conversationSummarySchema);

const tokenUsageSnakeSchema = z.object({
  input_tokens: z.number().finite(),
  output_tokens: z.number().finite(),
  cache_creation_tokens: z.number().finite().optional(),
  cache_read_tokens: z.number().finite().optional(),
});

const tokenUsageCamelSchema = z.object({
  inputTokens: z.number().finite(),
  outputTokens: z.number().finite(),
  cacheCreationTokens: z.number().finite().optional(),
  cacheReadTokens: z.number().finite().optional(),
});

const tokenUsageSchema = z.union([tokenUsageSnakeSchema, tokenUsageCamelSchema]);

const conversationMessageSnakeSchema = z
  .object({
    id: nonEmptyTrimmedString,
    role: z.enum(["user", "assistant", "tool"]),
    timestamp: z.number().finite(),
    blocks: z.array(jsonObjectSchema),
    usage: tokenUsageSchema.optional(),
    model: nullableTrimmedString.optional(),
    reasoning_tokens: z.number().finite().optional(),
    speed: nullableTrimmedString.optional(),
  })
  .passthrough();

const conversationMessageCamelSchema = z
  .object({
    id: nonEmptyTrimmedString,
    role: z.enum(["user", "assistant", "tool"]),
    timestamp: z.number().finite(),
    blocks: z.array(jsonObjectSchema),
    usage: tokenUsageSchema.optional(),
    model: nullableTrimmedString.optional(),
    reasoningTokens: z.number().finite().optional(),
    speed: nullableTrimmedString.optional(),
  })
  .passthrough();

const conversationMessageSchema = z.union([
  conversationMessageSnakeSchema,
  conversationMessageCamelSchema,
]);

const conversationPlanSnakeSchema = z
  .object({
    id: nonEmptyTrimmedString,
    slug: nonEmptyTrimmedString,
    title: nonEmptyTrimmedString,
    preview: z.string(),
    content: z.string(),
    provider: providerSchema,
    timestamp: z.number().finite(),
    session_id: nonEmptyTrimmedString.optional(),
    project_path: nonEmptyTrimmedString.optional(),
    route_slug: nullableTrimmedString.optional(),
    conversation_ref: nullableTrimmedString.optional(),
    model: nullableTrimmedString.optional(),
    source_path: nullableTrimmedString.optional(),
    explanation: nullableTrimmedString.optional(),
    steps: z.array(jsonObjectSchema).optional(),
  })
  .passthrough();

const conversationPlanCamelSchema = z
  .object({
    id: nonEmptyTrimmedString,
    slug: nonEmptyTrimmedString,
    title: nonEmptyTrimmedString,
    preview: z.string(),
    content: z.string(),
    provider: providerSchema,
    timestamp: z.number().finite(),
    sessionId: nonEmptyTrimmedString.optional(),
    projectPath: nonEmptyTrimmedString.optional(),
    routeSlug: nullableTrimmedString.optional(),
    conversationRef: nullableTrimmedString.optional(),
    model: nullableTrimmedString.optional(),
    sourcePath: nullableTrimmedString.optional(),
    explanation: nullableTrimmedString.optional(),
    steps: z.array(jsonObjectSchema).optional(),
  })
  .passthrough();

const conversationPlanSchema = z.union([
  conversationPlanSnakeSchema,
  conversationPlanCamelSchema,
]);

const subagentSnakeSchema = z
  .object({
    agent_id: nonEmptyTrimmedString,
    has_file: z.boolean(),
    project_path: nonEmptyTrimmedString,
    session_id: nonEmptyTrimmedString,
    route_slug: nullableTrimmedString.optional(),
    conversation_ref: nullableTrimmedString.optional(),
    description: nullableTrimmedString.optional(),
    subagent_type: nullableTrimmedString.optional(),
    nickname: nullableTrimmedString.optional(),
  })
  .passthrough();

const subagentCamelSchema = z
  .object({
    agentId: nonEmptyTrimmedString,
    hasFile: z.boolean(),
    projectPath: nonEmptyTrimmedString,
    sessionId: nonEmptyTrimmedString,
    routeSlug: nullableTrimmedString.optional(),
    conversationRef: nullableTrimmedString.optional(),
    description: nullableTrimmedString.optional(),
    subagentType: nullableTrimmedString.optional(),
    nickname: nullableTrimmedString.optional(),
  })
  .passthrough();

const subagentSchema = z.union([subagentSnakeSchema, subagentCamelSchema]);

const contextBucketSchema = z
  .object({
    label: z.string(),
    category: z.string(),
    input_tokens: z.number().finite().optional(),
    inputTokens: z.number().finite().optional(),
    output_tokens: z.number().finite().optional(),
    outputTokens: z.number().finite().optional(),
    cache_write_tokens: z.number().finite().optional(),
    cacheWriteTokens: z.number().finite().optional(),
    cache_read_tokens: z.number().finite().optional(),
    cacheReadTokens: z.number().finite().optional(),
    total_tokens: z.number().finite().optional(),
    totalTokens: z.number().finite().optional(),
    calls: z.number().finite(),
  })
  .passthrough();

const contextStepSchema = z
  .object({
    index: z.number().finite(),
    role: z.enum(["user", "assistant", "tool"]),
    label: z.string(),
    category: z.string(),
    timestamp: z.number().finite(),
    message_id: z.string().optional(),
    messageId: z.string().optional(),
    input_tokens: z.number().finite().optional(),
    inputTokens: z.number().finite().optional(),
    output_tokens: z.number().finite().optional(),
    outputTokens: z.number().finite().optional(),
    cache_write_tokens: z.number().finite().optional(),
    cacheWriteTokens: z.number().finite().optional(),
    cache_read_tokens: z.number().finite().optional(),
    cacheReadTokens: z.number().finite().optional(),
    total_tokens: z.number().finite().optional(),
    totalTokens: z.number().finite().optional(),
  })
  .passthrough();

const contextAnalyticsSchema = z
  .object({
    buckets: z.array(contextBucketSchema),
    steps: z.array(contextStepSchema),
  })
  .passthrough();

const contextWindowSchema = z
  .object({
    peak_context_window: z.number().finite().optional(),
    peakContextWindow: z.number().finite().optional(),
    api_calls: z.number().finite().optional(),
    apiCalls: z.number().finite().optional(),
    cumulative_tokens: z.number().finite().optional(),
    cumulativeTokens: z.number().finite().optional(),
  })
  .passthrough();

const openClawArtifactSchema = z
  .object({
    kind: z.string().optional(),
    path: z.string().optional(),
    status: z.string().optional(),
    canonical_session_id: z.string().optional(),
  })
  .catchall(jsonValueSchema);

const openClawProviderDetailSchema = z
  .object({
    artifact_inventory: z
      .object({
        live_transcript: openClawArtifactSchema.optional(),
        attached_archives: z.array(openClawArtifactSchema).optional(),
      })
      .catchall(jsonValueSchema),
    session_store: jsonObjectSchema.optional(),
    skills: jsonObjectSchema.optional(),
    system_prompt: jsonObjectSchema.optional(),
    transcript_diagnostics: jsonObjectSchema.optional(),
    usage_reconciliation: jsonObjectSchema.optional(),
    memory_store: jsonObjectSchema.optional(),
    raw: jsonObjectSchema.optional(),
  })
  .catchall(jsonValueSchema);

export const conversationProviderDetailSchema = z.object({
  kind: z.literal("openclaw"),
  openclaw: openClawProviderDetailSchema,
});

const conversationDetailSnakeSchema = z
  .object({
    session_id: nonEmptyTrimmedString,
    project_path: nonEmptyTrimmedString,
    provider: providerSchema.optional(),
    route_slug: nullableTrimmedString.optional(),
    conversation_ref: nullableTrimmedString.optional(),
    thread_type: threadTypeSchema.optional(),
    created_at: z.number().finite(),
    last_updated_at: z.number().finite(),
    is_running: z.boolean(),
    messages: z.array(conversationMessageSchema),
    plans: z.array(conversationPlanSchema),
    total_usage: tokenUsageSchema,
    model: nullableTrimmedString.optional(),
    git_branch: nullableTrimmedString.optional(),
    start_time: z.number().finite(),
    end_time: z.number().finite(),
    subagents: z.array(subagentSchema),
    context_analytics: contextAnalyticsSchema,
    context_window: contextWindowSchema,
    reasoning_effort: nullableTrimmedString.optional(),
    speed: nullableTrimmedString.optional(),
    total_reasoning_tokens: z.number().finite().nullable().optional(),
    provider_detail: conversationProviderDetailSchema.optional(),
  })
  .passthrough();

const openClawArtifactCamelSchema = z
  .object({
    kind: z.string().optional(),
    path: z.string().optional(),
    status: z.string().optional(),
    canonicalSessionId: z.string().optional(),
  })
  .catchall(jsonValueSchema);

const conversationProviderDetailCamelSchema = z.object({
  kind: z.literal("openclaw"),
  openclaw: z
    .object({
      artifactInventory: z
        .object({
          liveTranscript: openClawArtifactCamelSchema.optional(),
          attachedArchives: z.array(openClawArtifactCamelSchema).optional(),
        })
        .catchall(jsonValueSchema),
      sessionStore: jsonObjectSchema.optional(),
      skills: jsonObjectSchema.optional(),
      systemPrompt: jsonObjectSchema.optional(),
      transcriptDiagnostics: jsonObjectSchema.optional(),
      usageReconciliation: jsonObjectSchema.optional(),
      memoryStore: jsonObjectSchema.optional(),
      raw: jsonObjectSchema.optional(),
    })
    .catchall(jsonValueSchema),
});

const conversationDetailCamelSchema = z
  .object({
    sessionId: nonEmptyTrimmedString,
    projectPath: nonEmptyTrimmedString,
    provider: providerSchema.optional(),
    routeSlug: nullableTrimmedString.optional(),
    conversationRef: nullableTrimmedString.optional(),
    threadType: threadTypeSchema.optional(),
    createdAt: z.number().finite(),
    lastUpdatedAt: z.number().finite(),
    isRunning: z.boolean(),
    messages: z.array(conversationMessageSchema),
    plans: z.array(conversationPlanSchema),
    totalUsage: tokenUsageSchema,
    model: nullableTrimmedString.optional(),
    gitBranch: nullableTrimmedString.optional(),
    startTime: z.number().finite(),
    endTime: z.number().finite(),
    subagents: z.array(subagentSchema),
    contextAnalytics: contextAnalyticsSchema,
    contextWindow: contextWindowSchema,
    reasoningEffort: nullableTrimmedString.optional(),
    speed: nullableTrimmedString.optional(),
    totalReasoningTokens: z.number().finite().nullable().optional(),
    providerDetail: conversationProviderDetailCamelSchema.optional(),
  })
  .passthrough();

export const conversationDetailSchema = z.union([
  conversationDetailSnakeSchema,
  conversationDetailCamelSchema,
]);

export type ConversationSummaryPayload = z.infer<typeof conversationSummarySchema>;
export type ConversationDetailPayload = z.infer<typeof conversationDetailSchema>;
