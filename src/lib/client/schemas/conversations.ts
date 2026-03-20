import { z } from "zod";

import { nonEmptyTrimmedString } from "./shared.ts";

const threadTypeSchema = z.enum(["main", "subagent"]);
const nullableTrimmedString = z.union([z.string().trim(), z.null()]);
const countMapSchema = z.record(z.string(), z.number().int().nonnegative());

const conversationSummarySnakeSchema = z.object({
  session_id: nonEmptyTrimmedString,
  project_path: nonEmptyTrimmedString,
  project_name: nonEmptyTrimmedString,
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

export type ConversationSummaryPayload = z.infer<typeof conversationSummarySchema>;
