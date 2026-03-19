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
  threadType: "main" | "subagent";
  firstMessage: string;
  timestamp: number;
  createdAt: number;
  lastUpdatedAt: number;
  isRunning: boolean;
  messageCount: number;
  model?: string;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheCreationTokens: number;
  totalCacheReadTokens: number;
  toolUseCount: number;
  failedToolCallCount: number;
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

export interface ConversationDagNode {
  id: string;
  sessionId: string;
  parentSessionId?: string;
  projectPath: string;
  label: string;
  description?: string;
  nickname?: string;
  subagentType?: string;
  threadType: "main" | "subagent";
  hasTranscript: boolean;
  model?: string;
  messageCount: number;
  totalTokens: number;
  timestamp: number;
  depth: number;
  path: string;
  isRoot: boolean;
}

export interface ConversationDagEdge {
  id: string;
  source: string;
  target: string;
}

export interface ConversationDagStats {
  totalNodes: number;
  totalEdges: number;
  totalSubagentNodes: number;
  maxDepth: number;
  maxBreadth: number;
  leafCount: number;
  rootSubagentCount: number;
  totalMessages: number;
  totalTokens: number;
}

export interface ConversationDag {
  projectPath: string;
  rootSessionId: string;
  nodes: ConversationDagNode[];
  edges: ConversationDagEdge[];
  stats: ConversationDagStats;
}

export interface ConversationDagSummary extends ConversationSummary {
  dag: ConversationDagStats;
}

export interface OrchestrationInvocation {
  agent: string;
  role: string;
  command: string[];
  cwd: string;
  prompt: string;
  sessionId?: string | null;
  sessionIdField?: string | null;
  requestedSessionId?: string | null;
  outputText: string;
  rawStdout: string;
  rawStderr: string;
  exitCode: number;
  timedOut: boolean;
  startedAt: string;
  finishedAt: string;
  projectPath?: string;
  conversationPath?: string;
}

export type OrchestrationTaskStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "timed_out"
  | "skipped"
  | "blocked";

export type OrchestrationRunStatus =
  | "pending"
  | "planning"
  | "running"
  | "completed"
  | "failed"
  | "timed_out";

export interface OrchestrationTaskRecord {
  taskId: string;
  title: string;
  dependsOn: string[];
  status: OrchestrationTaskStatus;
  attempts: number;
  invocation: OrchestrationInvocation;
}

export interface OrchestrationDagNode {
  id: string;
  kind: "planner" | "task";
  label: string;
  description?: string;
  role: string;
  agent: string;
  sessionId?: string | null;
  projectPath?: string;
  conversationPath?: string;
  status: OrchestrationTaskStatus | OrchestrationRunStatus;
  isActive: boolean;
  attempts?: number;
  lastHeartbeatAt?: string | null;
  exitCode: number;
  timedOut: boolean;
  depth: number;
}

export interface OrchestrationDagEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface OrchestrationDagStats {
  totalNodes: number;
  totalEdges: number;
  maxDepth: number;
  maxBreadth: number;
  rootCount: number;
  providerBreakdown: Record<string, number>;
  timedOutCount: number;
  activeCount: number;
  pendingCount: number;
  failedCount: number;
  succeededCount: number;
}

export interface OrchestrationDag {
  nodes: OrchestrationDagNode[];
  edges: OrchestrationDagEdge[];
  stats: OrchestrationDagStats;
}

export interface OvernightOatsRunRecord {
  source: "overnight-oats";
  contractVersion: "oats-run-v1" | "oats-runtime-v1";
  runId: string;
  runTitle: string;
  repoRoot: string;
  configPath: string;
  runSpecPath: string;
  mode: string;
  integrationBranch: string;
  taskPrTarget: string;
  finalPrTarget: string;
  status: OrchestrationRunStatus;
  activeTaskId?: string | null;
  heartbeatAt?: string | null;
  finishedAt?: string | null;
  planner: OrchestrationInvocation | null;
  tasks: OrchestrationTaskRecord[];
  createdAt: string;
  lastUpdatedAt: string;
  isRunning: boolean;
  recordedAt: string;
  recordPath: string;
  dag: OrchestrationDag;
}

export type PrefectRunTone = "running" | "success" | "error" | "pending" | "unknown";
export type PrefectInfraTone = "healthy" | "warning" | "offline" | "unknown";

export interface PrefectOatsMetadata {
  runTitle?: string;
  sourcePath?: string;
  repoRoot?: string;
  configPath?: string;
  localMetadataPath?: string;
  artifactRoot?: string;
  repoLabel?: string;
  sourceLabel?: string;
  sourceHref?: string;
  configHref?: string;
  metadataHref?: string;
  artifactHref?: string;
}

export interface PrefectDeploymentRecord {
  deploymentId: string;
  deploymentName: string;
  flowId?: string;
  flowName?: string;
  workPoolName?: string;
  workQueueName?: string;
  status?: string;
  updatedAt?: string;
  tags: string[];
  oatsMetadata?: PrefectOatsMetadata;
}

export interface PrefectFlowRunRecord {
  flowRunId: string;
  flowRunName?: string;
  deploymentId?: string;
  deploymentName?: string;
  flowId?: string;
  flowName?: string;
  workPoolName?: string;
  workQueueName?: string;
  stateType?: string;
  stateName?: string;
  createdAt?: string;
  updatedAt?: string;
  oatsMetadata?: PrefectOatsMetadata;
  statusTone: PrefectRunTone;
  statusLabel: string;
  isActive: boolean;
}

export interface PrefectWorkerRecord {
  workerId: string;
  workerName: string;
  workPoolName?: string;
  status?: string;
  lastHeartbeatAt?: string;
  statusTone: PrefectInfraTone;
  isOnline: boolean;
}

export interface PrefectWorkPoolRecord {
  workPoolId: string;
  workPoolName: string;
  type?: string;
  status?: string;
  isPaused: boolean;
  concurrencyLimit?: number;
  workerCount: number;
  onlineWorkerCount: number;
  statusTone: PrefectInfraTone;
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

export type PlanProvider = "claude" | "codex";

export interface ConversationPlanStep {
  step: string;
  status: string;
}

export interface ConversationPlan {
  id: string;
  slug: string;
  title: string;
  preview: string;
  content: string;
  provider: PlanProvider;
  timestamp: number;
  sessionId: string;
  projectPath: string;
  model?: string;
  sourcePath?: string;
  explanation?: string;
  steps?: ConversationPlanStep[];
}

export interface ProcessedConversation {
  sessionId: string;
  projectPath: string;
  createdAt: number;
  lastUpdatedAt: number;
  isRunning: boolean;
  messages: ProcessedMessage[];
  plans: ConversationPlan[];
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
  provider: PlanProvider;
  timestamp: number;
  model?: string;
  sourcePath?: string;
  sessionId?: string;
  projectPath?: string;
}

export interface PlanDetail {
  id: string;
  slug: string;
  title: string;
  content: string;
  provider: PlanProvider;
  timestamp: number;
  model?: string;
  sourcePath?: string;
  sessionId?: string;
  projectPath?: string;
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

export interface AnalyticsRateValue {
  perHour: number;
  perDay: number;
  perWeek: number;
  perMonth: number;
}

export interface AnalyticsRates {
  spend: AnalyticsRateValue;
  totalTokens: AnalyticsRateValue;
  inputTokens: AnalyticsRateValue;
  outputTokens: AnalyticsRateValue;
  cacheWriteTokens: AnalyticsRateValue;
  cacheReadTokens: AnalyticsRateValue;
  reasoningTokens: AnalyticsRateValue;
  conversations: AnalyticsRateValue;
  toolCalls: AnalyticsRateValue;
  failedToolCalls: AnalyticsRateValue;
  subagents: AnalyticsRateValue;
}

export interface AnalyticsTimeSeriesPoint {
  key: string;
  label: string;
  start: string;
  end: string;
  estimatedCost: number;
  claudeEstimatedCost: number;
  codexEstimatedCost: number;
  inputTokens: number;
  outputTokens: number;
  cacheWriteTokens: number;
  cacheReadTokens: number;
  reasoningTokens: number;
  totalTokens: number;
  conversations: number;
  toolCalls: number;
  failedToolCalls: number;
  toolErrorRatePct: number;
  subagents: number;
  claudeInputTokens: number;
  claudeOutputTokens: number;
  claudeCacheWriteTokens: number;
  claudeCacheReadTokens: number;
  claudeReasoningTokens: number;
  claudeTotalTokens: number;
  claudeConversations: number;
  claudeToolCalls: number;
  claudeFailedToolCalls: number;
  claudeToolErrorRatePct: number;
  claudeSubagents: number;
  codexInputTokens: number;
  codexOutputTokens: number;
  codexCacheWriteTokens: number;
  codexCacheReadTokens: number;
  codexReasoningTokens: number;
  codexTotalTokens: number;
  codexConversations: number;
  codexToolCalls: number;
  codexFailedToolCalls: number;
  codexToolErrorRatePct: number;
  codexSubagents: number;
}

export interface AnalyticsTimeSeries {
  hourly: AnalyticsTimeSeriesPoint[];
  daily: AnalyticsTimeSeriesPoint[];
  weekly: AnalyticsTimeSeriesPoint[];
  monthly: AnalyticsTimeSeriesPoint[];
}

export type SupportedProvider = "claude" | "codex";

export interface ProviderSubscriptionSetting {
  provider: SupportedProvider;
  hasSubscription: boolean;
  monthlyCost: number;
  updatedAt: string;
}

export interface SubscriptionSettings {
  claude: ProviderSubscriptionSetting;
  codex: ProviderSubscriptionSetting;
}

export interface AnalyticsData {
  totalConversations: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheCreationTokens: number;
  totalCacheReadTokens: number;
  totalReasoningTokens: number;
  totalToolCalls: number;
  totalFailedToolCalls: number;
  modelBreakdown: Record<string, number>;
  toolBreakdown: Record<string, number>;
  subagentTypeBreakdown: Record<string, number>;
  modelBreakdownByProvider: Record<string, ProviderBreakdown>;
  toolBreakdownByProvider: Record<string, ProviderBreakdown>;
  subagentTypeBreakdownByProvider: Record<string, ProviderBreakdown>;
  dailyUsage: DailyUsage[];
  rates: AnalyticsRates;
  timeSeries: AnalyticsTimeSeries;
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

export interface DatabaseColumnSchema {
  name: string;
  type: string;
  nullable: boolean;
  defaultValue?: string | null;
  isPrimaryKey: boolean;
  references?: string | null;
}

export interface DatabaseTableSchema {
  name: string;
  rowCount: number;
  columns: DatabaseColumnSchema[];
}

export type DatabaseStatusKey = "sqlite" | "duckdb";
export type DatabaseRole = "metadata" | "inspection";
export type DatabaseAvailability = "ready" | "missing" | "unreachable";

export interface DatabaseArtifactStatus {
  key: DatabaseStatusKey;
  label: string;
  engine: string;
  role: DatabaseRole;
  availability: DatabaseAvailability;
  note?: string | null;
  error?: string | null;
  path?: string | null;
  target?: string | null;
  publicPath?: string | null;
  docsUrl?: string | null;
  tableCount: number;
  tables: DatabaseTableSchema[];
}

export interface DatabaseStatus {
  status: "idle" | "running" | "completed" | "failed";
  trigger?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  durationMs?: number | null;
  error?: string | null;
  lastSuccessfulRefreshAt?: string | null;
  idempotencyKey?: string | null;
  scopeLabel?: string;
  windowDays?: number;
  windowStart?: string | null;
  windowEnd?: string | null;
  sourceConversationCount?: number;
  refreshIntervalMinutes: number;
  runtime: {
    analyticsReadBackend: "legacy";
    conversationSummaryReadBackend: "legacy";
  };
  databases: {
    sqlite: DatabaseArtifactStatus;
    duckdb: DatabaseArtifactStatus;
  };
}

export interface EvaluationPrompt {
  promptId: string;
  name: string;
  description?: string | null;
  promptText: string;
  isDefault: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationEvaluation {
  evaluationId: string;
  conversationId: string;
  promptId?: string | null;
  provider: "claude" | "codex";
  model: string;
  status: "running" | "completed" | "failed";
  scope: "full" | "failed_tool_calls" | "guided_subset";
  selectionInstruction?: string | null;
  promptName: string;
  promptText: string;
  reportMarkdown?: string | null;
  rawOutput?: string | null;
  errorMessage?: string | null;
  command: string;
  createdAt: string;
  finishedAt?: string | null;
  durationMs?: number | null;
}
