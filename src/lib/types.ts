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
  provider?: FrontendProvider;
  routeSlug?: string;
  conversationRef?: string;
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
  recordSource?: string;
  sourcePath?: string;
  sourceFileModifiedAt?: number;
}

export interface SubagentInfo {
  agentId: string;
  description?: string;
  subagentType?: string;
  nickname?: string;
  hasFile: boolean;
  projectPath: string;
  sessionId: string;
  routeSlug?: string | null;
  conversationRef?: string | null;
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
  path?: string | null;
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
  exitCode?: number;
  timedOut: boolean;
  startedAt: string;
  finishedAt?: string | null;
  projectPath?: string | null;
  conversationPath?: string | null;
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

export type OrchestrationStackStatus =
  | "building"
  | "awaiting_task_merge"
  | "resolving_conflict"
  | "blocked"
  | "ready_for_final_review"
  | "completed";

export type OrchestrationStatusTone =
  | "running"
  | "success"
  | "error"
  | "pending"
  | "warning"
  | "unknown";

export interface OrchestrationTaskRecord {
  taskId: string;
  title: string;
  dependsOn: string[];
  parentBranch?: string | null;
  status: OrchestrationTaskStatus;
  attempts: number;
  taskPr?: OrchestrationTaskPullRequest | null;
  operationHistory: OrchestrationOperationHistoryEntry[];
  invocation: OrchestrationInvocation | null;
}

export interface OrchestrationFeatureBranch {
  name: string;
  baseBranch?: string | null;
}

export interface OrchestrationReviewSummary {
  blockingState: "clear" | "changes_requested" | "commented" | "unknown";
  approvals: number;
  changesRequested: number;
}

export interface OrchestrationTaskPullRequest {
  number?: number | null;
  url?: string | null;
  state: "not_created" | "open" | "merged" | "closed" | "blocked";
  mergeGateStatus:
    | "not_ready"
    | "awaiting_checks"
    | "awaiting_review_clearance"
    | "merge_ready"
    | "merged";
  baseBranch?: string | null;
  headBranch?: string | null;
  mergeability?: string | null;
  checksSummary: Record<string, unknown>;
  reviewSummary?: OrchestrationReviewSummary | null;
  snapshotSource?: string | null;
  lastRefreshedAt?: string | null;
  isStale: boolean;
}

export interface OrchestrationFinalPullRequest {
  number?: number | null;
  url?: string | null;
  state: "not_created" | "open" | "ready_for_review" | "merged" | "closed";
  reviewGateStatus: "not_created" | "awaiting_human" | "merged";
  baseBranch?: string | null;
  headBranch?: string | null;
  checksSummary: Record<string, unknown>;
  snapshotSource?: string | null;
  lastRefreshedAt?: string | null;
  isStale: boolean;
}

export interface OrchestrationOperationHistoryEntry {
  kind: string;
  status: "started" | "succeeded" | "failed";
  sessionId?: string | null;
  startedAt: string;
  finishedAt?: string | null;
  details: Record<string, unknown>;
}

export interface OrchestrationDagNode {
  id: string;
  kind: "planner" | "task";
  label: string;
  description?: string;
  role: string;
  agent: string;
  sessionId?: string | null;
  projectPath?: string | null;
  conversationPath?: string | null;
  status: OrchestrationTaskStatus | OrchestrationRunStatus;
  isActive: boolean;
  isStale?: boolean;
  statusTone?: OrchestrationStatusTone;
  statusLabel?: string;
  attempts?: number;
  lastHeartbeatAt?: string | null;
  exitCode?: number | null;
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

export interface OrchestrationRunEvaluationConversation {
  nodeId: string;
  label: string;
  role: string;
  agent: string;
  status: OrchestrationTaskStatus | OrchestrationRunStatus;
  taskId?: string | null;
  sessionId?: string | null;
  projectPath?: string | null;
  conversationPath?: string | null;
  startedAt: string;
  finishedAt?: string | null;
  hasSessionLink: boolean;
}

export interface OrchestrationRunEvaluationSummary {
  conversationCount: number;
  linkedConversationCount: number;
  missingConversationCount: number;
  activeConversationCount: number;
  failedConversationCount: number;
  providerBreakdown: Record<string, number>;
}

export interface OrchestrationRunEvaluation {
  summary: OrchestrationRunEvaluationSummary;
  conversations: OrchestrationRunEvaluationConversation[];
}

export interface OvernightOatsRunRecord {
  source: "overnight-oats";
  contractVersion:
    | "oats-run-v1"
    | "oats-run-v2"
    | "oats-runtime-v1"
    | "oats-runtime-v2";
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
  stackStatus?: OrchestrationStackStatus | null;
  featureBranch?: OrchestrationFeatureBranch | null;
  activeTaskId?: string | null;
  heartbeatAt?: string | null;
  finishedAt?: string | null;
  planner: OrchestrationInvocation | null;
  tasks: OrchestrationTaskRecord[];
  finalPr?: OrchestrationFinalPullRequest | null;
  operationHistory: OrchestrationOperationHistoryEntry[];
  createdAt: string;
  lastUpdatedAt: string;
  isRunning: boolean;
  recordedAt: string;
  recordPath: string;
  dag: OrchestrationDag;
  evaluation?: OrchestrationRunEvaluation;
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
  role: "user" | "assistant" | "tool";
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

export type FrontendProvider = "claude" | "codex" | "openclaw" | "opencloud";

export type PlanProvider = FrontendProvider;

export interface CanonicalConversationLink {
  sessionId?: string;
  projectPath?: string;
  routeSlug?: string | null;
  conversationRef?: string | null;
}

export interface ConversationRouteResolution {
  conversationRef: string;
  routeSlug: string;
  projectPath: string;
  sessionId: string;
  threadType: "main" | "subagent";
  parentSessionId?: string;
}

export interface ConversationPlanStep {
  step: string;
  status: string;
}

export interface ConversationPlan extends CanonicalConversationLink {
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
  provider?: FrontendProvider;
  providerDetail?: ProviderDetail;
  routeSlug?: string;
  conversationRef?: string;
  threadType?: "main" | "subagent";
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

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];

export interface JsonObject {
  [key: string]: JsonValue | undefined;
}

export interface OpenClawArtifactRecord extends JsonObject {
  kind?: string;
  path?: string;
  status?: string;
  canonicalSessionId?: string;
}

export interface OpenClawArtifactInventory extends JsonObject {
  liveTranscript?: OpenClawArtifactRecord;
  attachedArchives: OpenClawArtifactRecord[];
}

export interface OpenClawSkillsDetail extends JsonObject {
  prompt?: string;
  declared?: JsonObject[];
  resolved?: JsonObject[];
}

export interface OpenClawSystemPromptDetail extends JsonObject {
  workspaceDir?: string;
  sandboxMode?: string;
}

export interface OpenClawUsageReconciliation extends JsonObject {
  transcriptTotalTokens?: number;
  storeTotalTokens?: number;
}

export interface OpenClawMemoryWorkspaceLink extends JsonObject {
  workspaceDir?: string;
  matchedPrefix?: string;
  confidence?: string;
}

export interface OpenClawMemoryStoreDetail extends JsonObject {
  path?: string;
  tables?: string[];
  counts?: Record<string, number>;
  coverage?: JsonObject;
  workspaceLink?: OpenClawMemoryWorkspaceLink;
  rawRows?: JsonObject[];
}

export interface OpenClawProviderDetail extends JsonObject {
  artifactInventory: OpenClawArtifactInventory;
  sessionStore?: JsonObject;
  skills?: OpenClawSkillsDetail;
  systemPrompt?: OpenClawSystemPromptDetail;
  transcriptDiagnostics?: JsonObject;
  usageReconciliation?: OpenClawUsageReconciliation;
  memoryStore?: OpenClawMemoryStoreDetail;
  raw?: JsonObject;
}

export interface OpenClawConversationProviderDetail {
  kind: "openclaw";
  openclaw: OpenClawProviderDetail;
}

export type ProviderDetail = OpenClawConversationProviderDetail;

export interface ProcessedMessage {
  id: string;
  role: "user" | "assistant" | "tool";
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

export interface PlanDetail extends CanonicalConversationLink {
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
  openclaw?: number;
  opencloud?: number;
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
  openclawEstimatedCost?: number;
  openclawInputTokens?: number;
  openclawOutputTokens?: number;
  openclawCacheWriteTokens?: number;
  openclawCacheReadTokens?: number;
  openclawReasoningTokens?: number;
  openclawTotalTokens?: number;
  openclawConversations?: number;
  openclawToolCalls?: number;
  openclawFailedToolCalls?: number;
  openclawToolErrorRatePct?: number;
  openclawSubagents?: number;
  opencloudEstimatedCost?: number;
  opencloudInputTokens?: number;
  opencloudOutputTokens?: number;
  opencloudCacheWriteTokens?: number;
  opencloudCacheReadTokens?: number;
  opencloudReasoningTokens?: number;
  opencloudTotalTokens?: number;
  opencloudConversations?: number;
  opencloudToolCalls?: number;
  opencloudFailedToolCalls?: number;
  opencloudToolErrorRatePct?: number;
  opencloudSubagents?: number;
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

export type SupportedProvider = FrontendProvider;

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
  openclawInputTokens?: number;
  openclawOutputTokens?: number;
  openclawCacheWriteTokens?: number;
  openclawCacheReadTokens?: number;
  openclawConversations?: number;
  openclawSubagents?: number;
  opencloudInputTokens?: number;
  opencloudOutputTokens?: number;
  opencloudCacheWriteTokens?: number;
  opencloudCacheReadTokens?: number;
  opencloudConversations?: number;
  opencloudSubagents?: number;
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
  sizeBytes?: number | null;
  sizeDisplay?: string | null;
  columns: DatabaseColumnSchema[];
  servingClass?: string;
  integrationType?: string;
  fastapiRoutes?: string[];
  sqlalchemyModel?: string | null;
  note?: string | null;
}

export interface DatabaseLoadMetric {
  label: string;
  value?: number | null;
  displayValue?: string | null;
}

export type DatabaseStatusKey =
  | "frontend_cache"
  | "sqlite"
  | "duckdb";
export type DatabaseRole = "cache" | "metadata" | "inspection" | "orchestration";
export type DatabaseAvailability = "ready" | "missing" | "unreachable";

export interface DatabaseArtifactStatus {
  key: DatabaseStatusKey;
  label: string;
  engine: string;
  role: DatabaseRole;
  availability: DatabaseAvailability;
  health?: string | null;
  operationalStatus?: string | null;
  note?: string | null;
  error?: string | null;
  path?: string | null;
  target?: string | null;
  publicPath?: string | null;
  docsUrl?: string | null;
  tableCount: number;
  sizeBytes?: number | null;
  sizeDisplay?: string | null;
  inventorySummary?: string | null;
  load: DatabaseLoadMetric[];
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
    frontendCache: DatabaseArtifactStatus;
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
  provider: FrontendProvider;
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
