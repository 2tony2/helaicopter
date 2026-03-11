// Raw JSONL event types from ~/.claude/ conversation files

export interface RawEvent {
  type: "user" | "assistant" | "progress" | "file-history-snapshot";
  uuid: string;
  parentUuid?: string;
  timestamp: number | string;
  sessionId?: string;
  cwd?: string;
  gitBranch?: string;
  slug?: string;
  isSidechain?: boolean;
  agentId?: string;
  message?: RawMessage;
  requestId?: string;
  planContent?: string;
  toolUseResult?: ToolUseResultMeta;
  sourceToolAssistantUUID?: string;
  data?: unknown;
  parentToolUseID?: string;
  toolUseID?: string;
  messageId?: string;
  snapshot?: unknown;
  isSnapshotUpdate?: boolean;
}

export interface ToolUseResultMeta {
  isAsync?: boolean;
  status?: string;
  agentId?: string;
  description?: string;
  prompt?: string;
  outputFile?: string;
  [key: string]: unknown;
}

export interface RawMessage {
  role: "user" | "assistant";
  type?: string;
  model?: string;
  content: RawContentBlock[] | string;
  usage?: TokenUsage;
  stop_reason?: string;
}

export type RawContentBlock =
  | TextBlock
  | ThinkingBlock
  | ToolUseBlock
  | ToolResultBlock;

export interface TextBlock {
  type: "text";
  text: string;
}

export interface ThinkingBlock {
  type: "thinking";
  thinking: string;
  signature?: string;
}

export interface ToolUseBlock {
  type: "tool_use";
  id: string;
  name: string;
  input: Record<string, unknown>;
  caller?: unknown;
}

export interface ToolResultBlock {
  type: "tool_result";
  tool_use_id: string;
  content: string | RawContentBlock[];
  is_error?: boolean;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cache_creation_input_tokens?: number;
  cache_read_input_tokens?: number;
  cache_creation?: {
    ephemeral_5m_input_tokens?: number;
    ephemeral_1h_input_tokens?: number;
  };
  service_tier?: string;
  inference_geo?: string;
  speed?: string; // "standard" | "fast"
}

// Processed display models

export interface ConversationSummary {
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
  reasoningEffort?: string; // Codex: "low" | "medium" | "high"
  speed?: string; // Claude: "standard" | "fast"
  totalReasoningTokens?: number; // Codex only
}

export interface SubagentInfo {
  agentId: string;
  description?: string;
  subagentType?: string;
  nickname?: string;
  hasFile: boolean;
  projectPath: string;
  sessionId: string;
}

/** Per-tool or per-category context breakdown */
export interface ContextBucket {
  label: string;
  category: "tool" | "mcp" | "subagent" | "thinking" | "conversation";
  inputTokens: number;
  outputTokens: number;
  cacheWriteTokens: number;
  cacheReadTokens: number;
  totalTokens: number;
  calls: number;
}

/** Per-step (per-message) context entry for the sorted list */
export interface ContextStep {
  messageId: string;
  index: number;
  role: "user" | "assistant";
  label: string;
  category: ContextBucket["category"];
  timestamp: number;
  inputTokens: number;
  outputTokens: number;
  cacheWriteTokens: number;
  cacheReadTokens: number;
  totalTokens: number;
}

export interface ContextAnalytics {
  buckets: ContextBucket[];
  steps: ContextStep[];
}

export interface ContextWindowStats {
  /** Largest single API call context (input + cache_write + cache_read) */
  peakContextWindow: number;
  /** Number of API calls in the conversation */
  apiCalls: number;
  /** Sum of all tokens across all API calls (what the cumulative "total" shows) */
  cumulativeTokens: number;
}

export interface ProcessedConversation {
  sessionId: string;
  projectPath: string;
  messages: ProcessedMessage[];
  totalUsage: TokenUsage;
  model?: string;
  gitBranch?: string;
  startTime: number;
  endTime: number;
  subagents: SubagentInfo[];
  contextAnalytics: ContextAnalytics;
  contextWindow: ContextWindowStats;
  reasoningEffort?: string; // Codex: "low" | "medium" | "high"
  speed?: string; // Claude: "standard" | "fast"
  totalReasoningTokens?: number; // Codex only
}

export interface ProcessedMessage {
  id: string;
  role: "user" | "assistant";
  timestamp: number;
  blocks: DisplayBlock[];
  usage?: TokenUsage;
  model?: string;
  reasoningTokens?: number; // Codex: reasoning_output_tokens for this step
  speed?: string; // Claude: "standard" | "fast" for this message
}

export type DisplayBlock =
  | DisplayTextBlock
  | DisplayThinkingBlock
  | DisplayToolCallBlock;

export interface DisplayTextBlock {
  type: "text";
  text: string;
}

export interface DisplayThinkingBlock {
  type: "thinking";
  thinking: string;
  charCount: number;
}

export interface DisplayToolCallBlock {
  type: "tool_call";
  toolUseId: string;
  toolName: string;
  input: Record<string, unknown>;
  result?: string;
  isError?: boolean;
}

// History entry from ~/.claude/history.jsonl
export interface HistoryEntry {
  display: string;
  pastedContents?: Record<string, unknown>;
  timestamp: number;
  project?: string;
}

// Plan
export interface PlanSummary {
  id: string;
  slug: string;
  title: string;
  preview: string;
}

export interface PlanDetail {
  id: string;
  slug: string;
  title: string;
  content: string;
}

// Project info
export interface ProjectInfo {
  encodedPath: string;
  displayName: string;
  fullPath: string;
  sessionCount: number;
  lastActivity: number;
}

// Analytics
export interface AnalyticsCostBreakdown {
  inputCost: number;
  outputCost: number;
  cacheWriteCost: number;
  cacheReadCost: number;
  longContextPremium: number;
  longContextConversations: number;
  totalCost: number;
}

export interface AnalyticsCostBreakdownMap {
  [key: string]: AnalyticsCostBreakdown;
}

export interface ProviderBreakdown {
  claude: number;
  codex: number;
}

export interface AnalyticsData {
  totalConversations: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheCreationTokens: number;
  totalCacheReadTokens: number;
  totalToolCalls: number;
  modelBreakdown: Record<string, number>;
  toolBreakdown: Record<string, number>;
  subagentTypeBreakdown: Record<string, number>;
  modelBreakdownByProvider: Record<string, ProviderBreakdown>;
  toolBreakdownByProvider: Record<string, ProviderBreakdown>;
  subagentTypeBreakdownByProvider: Record<string, ProviderBreakdown>;
  dailyUsage: DailyUsage[];
  estimatedCost: number;
  costBreakdown: AnalyticsCostBreakdown;
  costBreakdownByProvider: AnalyticsCostBreakdownMap;
  costBreakdownByModel: AnalyticsCostBreakdownMap;
}

export interface DailyUsage {
  date: string;
  inputTokens: number;
  outputTokens: number;
  cacheWriteTokens: number;
  cacheReadTokens: number;
  conversations: number;
  subagents: number;
  claudeInputTokens: number;
  claudeOutputTokens: number;
  claudeCacheWriteTokens: number;
  claudeCacheReadTokens: number;
  codexInputTokens: number;
  codexOutputTokens: number;
  codexCacheWriteTokens: number;
  codexCacheReadTokens: number;
  claudeConversations: number;
  codexConversations: number;
  claudeSubagents: number;
  codexSubagents: number;
}
