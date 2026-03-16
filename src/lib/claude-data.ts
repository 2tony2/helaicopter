import { readdir, readFile, stat } from "fs/promises";
import { join } from "path";
import {
  PROJECTS_DIR,
  PLANS_DIR,
  HISTORY_FILE,
  TASKS_DIR,
} from "./constants";
import {
  extractConversationSummary,
  parseJsonlFile,
} from "./jsonl-parser";
import {
  extractClaudePlans,
  processConversation,
} from "./conversation-processor";
import { projectDirToDisplayName } from "./path-encoding";
import { summaryCache, conversationCache } from "./cache";
import type {
  ProjectInfo,
  ConversationSummary,
  ProcessedConversation,
  PlanSummary,
  PlanDetail,
  HistoryEntry,
  AnalyticsData,
  AnalyticsCostBreakdown,
  AnalyticsRates,
  AnalyticsTimeSeries,
  AnalyticsTimeSeriesPoint,
  DailyUsage,
  SubagentInfo,
  ProviderBreakdown,
} from "./types";
import { calculateCost } from "./pricing";
import {
  listCodexConversations,
  getCodexConversation,
  getCodexHistory,
  listCodexPlans,
  getCodexPlan,
} from "./codex-data";
import {
  decodePlanId,
  encodePlanId,
  summarizePlanContent,
} from "./plan-utils";
import {
  getHistoricalConversationStore,
} from "./historical-conversation-store";
import { startOfTodayMs } from "./time-windows";

const TIME_SERIES_KEYS = ["hourly", "daily", "weekly", "monthly"] as const;
type TimeSeriesKey = (typeof TIME_SERIES_KEYS)[number];

const historicalConversationStore = getHistoricalConversationStore();

function startOfUtcHour(timestamp: number): Date {
  const date = new Date(timestamp);
  date.setUTCMinutes(0, 0, 0);
  return date;
}

function startOfUtcDay(timestamp: number): Date {
  const date = new Date(timestamp);
  date.setUTCHours(0, 0, 0, 0);
  return date;
}

function startOfUtcWeek(timestamp: number): Date {
  const date = startOfUtcDay(timestamp);
  const day = date.getUTCDay();
  const delta = (day + 6) % 7;
  date.setUTCDate(date.getUTCDate() - delta);
  return date;
}

function startOfUtcMonth(timestamp: number): Date {
  const date = new Date(timestamp);
  date.setUTCDate(1);
  date.setUTCHours(0, 0, 0, 0);
  return date;
}

function getBucketStart(timestamp: number, key: TimeSeriesKey): Date {
  switch (key) {
    case "hourly":
      return startOfUtcHour(timestamp);
    case "daily":
      return startOfUtcDay(timestamp);
    case "weekly":
      return startOfUtcWeek(timestamp);
    case "monthly":
      return startOfUtcMonth(timestamp);
  }
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
  const results: AnalyticsTimeSeriesPoint[] = [];
  const byKey = new Map(entries);

  for (let cursor = first; cursor <= last; cursor = getNextBucketStart(cursor, key)) {
    const bucketKey = cursor.toISOString();
    results.push(byKey.get(bucketKey) || createEmptyTimeSeriesPoint(cursor, key));
  }

  return results;
}

function buildRateValue(total: number, hours: number, days: number): AnalyticsRates["spend"] {
  return {
    perHour: total / hours,
    perDay: total / days,
    perWeek: (total / days) * 7,
    perMonth: (total / days) * 30,
  };
}

function hasLongContextPremium(model?: string): boolean {
  if (!model) {
    return false;
  }

  return (
    model.includes("opus-4-6") ||
    model.includes("opus-4-5") ||
    model.includes("sonnet-4-6") ||
    model.includes("sonnet-4-5") ||
    model.includes("sonnet-4")
  );
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

async function listClaudeSessionPlans(): Promise<PlanSummary[]> {
  const plans: PlanSummary[] = [];

  try {
    const entries = await readdir(PROJECTS_DIR, { withFileTypes: true });

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;

      const projectDir = join(PROJECTS_DIR, entry.name);
      const files = await readdir(projectDir).catch(() => []);

      for (const file of files) {
        if (!file.endsWith(".jsonl")) continue;

        const sessionId = file.replace(".jsonl", "");
        const events = await parseJsonlFile(join(projectDir, file)).catch(() => []);
        plans.push(
          ...extractClaudePlans(events, sessionId, entry.name).map((plan) => ({
            id: plan.id,
            slug: plan.slug,
            title: plan.title,
            preview: plan.preview,
            provider: plan.provider,
            timestamp: plan.timestamp,
            model: plan.model,
            sourcePath: join(projectDir, file),
            sessionId: plan.sessionId,
            projectPath: plan.projectPath,
          }))
        );
      }
    }
  } catch {
    return [];
  }

  return plans;
}

async function getClaudeSessionPlan(id: string): Promise<PlanDetail | null> {
  const source = decodePlanId(id);
  if (!source || source.kind !== "claude-session") return null;

  try {
    const events = await parseJsonlFile(
      join(PROJECTS_DIR, source.projectPath, `${source.sessionId}.jsonl`)
    );
    const plan = extractClaudePlans(
      events,
      source.sessionId,
      source.projectPath
    ).find((entry) => entry.id === id);
    if (!plan) return null;

    return {
      id: plan.id,
      slug: plan.slug,
      title: plan.title,
      content: plan.content,
      provider: plan.provider,
      timestamp: plan.timestamp,
      model: plan.model,
      sourcePath: join(
        PROJECTS_DIR,
        source.projectPath,
        `${source.sessionId}.jsonl`
      ),
      sessionId: plan.sessionId,
      projectPath: plan.projectPath,
    };
  } catch {
    return null;
  }
}

async function listFilePlans(): Promise<PlanSummary[]> {
  try {
    const files = await readdir(PLANS_DIR);
    const plans: PlanSummary[] = [];

    for (const file of files) {
      if (!file.endsWith(".md")) continue;
      const slug = file.replace(".md", "");
      const filePath = join(PLANS_DIR, file);
      const content = await readFile(filePath, "utf-8");
      const metadata = summarizePlanContent(content, slug);
      const fileStat = await stat(filePath).catch(() => null);

      plans.push({
        id: encodePlanId({ kind: "file", slug }),
        ...metadata,
        provider: "claude",
        timestamp: fileStat?.mtimeMs ?? 0,
        sourcePath: filePath,
      });
    }

    return plans;
  } catch {
    return [];
  }
}

export async function listProjects(): Promise<ProjectInfo[]> {
  try {
    const entries = await readdir(PROJECTS_DIR, { withFileTypes: true });
    const projects: ProjectInfo[] = [];

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;

      const projectDir = join(PROJECTS_DIR, entry.name);
      const files = await readdir(projectDir).catch(() => []);
      const jsonlFiles = files.filter((f) => f.endsWith(".jsonl"));

      let lastActivity = 0;
      for (const f of jsonlFiles) {
        try {
          const s = await stat(join(projectDir, f));
          if (s.mtimeMs > lastActivity) lastActivity = s.mtimeMs;
        } catch {
          // skip
        }
      }

      if (jsonlFiles.length > 0) {
        projects.push({
          encodedPath: entry.name,
          displayName: projectDirToDisplayName(entry.name),
          fullPath: projectDir,
          sessionCount: jsonlFiles.length,
          lastActivity,
        });
      }
    }

    // Add Codex projects by aggregating Codex conversations
    try {
      const codexConvs = await listCodexConversations();
      const codexProjectMap = new Map<
        string,
        { displayName: string; count: number; lastActivity: number }
      >();
      for (const conv of codexConvs) {
        const existing = codexProjectMap.get(conv.projectPath) || {
          displayName: conv.projectName,
          count: 0,
          lastActivity: 0,
        };
        existing.count++;
        if (conv.timestamp > existing.lastActivity)
          existing.lastActivity = conv.timestamp;
        codexProjectMap.set(conv.projectPath, existing);
      }
      for (const [encodedPath, info] of codexProjectMap) {
        projects.push({
          encodedPath,
          displayName: info.displayName,
          fullPath: encodedPath,
          sessionCount: info.count,
          lastActivity: info.lastActivity,
        });
      }
    } catch {
      // Codex data not available
    }

    return projects.sort((a, b) => b.lastActivity - a.lastActivity);
  } catch {
    return [];
  }
}

export async function listRawConversations(
  projectFilter?: string,
  days?: number,
  options?: {
    dayScope?: "all" | "today" | "beforeToday";
  }
): Promise<ConversationSummary[]> {
  const conversations: ConversationSummary[] = [];
  // Use file mtime to skip files older than the cutoff — avoids expensive parsing
  const cutoffMs = days
    ? Date.now() - days * 24 * 60 * 60 * 1000
    : 0;
  const dayScope = options?.dayScope ?? "all";
  const todayStartMs = startOfTodayMs();

  try {
    const entries = await readdir(PROJECTS_DIR, { withFileTypes: true });

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (projectFilter && entry.name !== projectFilter) continue;

      const projectDir = join(PROJECTS_DIR, entry.name);
      const files = await readdir(projectDir).catch(() => []);

      for (const file of files) {
        if (!file.endsWith(".jsonl")) continue;

        const filePath = join(projectDir, file);

        // Fast mtime check — skip files not modified within the window
        if (cutoffMs) {
          try {
            const s = await stat(filePath);
            if (s.mtimeMs < cutoffMs) continue;
          } catch {
            continue;
          }
        }

        const sessionId = file.replace(".jsonl", "");

        // Check cache first
        const cached = await summaryCache.get(filePath);
        if (cached && (cached as { _summaryCacheVersion?: number })._summaryCacheVersion === 2) {
          const c = cached as ConversationSummary;
          // Even cached entries must pass the timestamp cutoff
          if (cutoffMs && c.timestamp && c.timestamp < cutoffMs) continue;
          if (dayScope === "today" && c.timestamp < todayStartMs) continue;
          if (dayScope === "beforeToday" && c.timestamp >= todayStartMs) continue;
          conversations.push(c);
          continue;
        }

        try {
          const summary = await extractConversationSummary(filePath);

          // Fast readdir counts for subagents and tasks
          const subagentDir = join(projectDir, sessionId, "subagents");
          let subagentCount = 0;
          try {
            const subs = await readdir(subagentDir);
            subagentCount = subs.filter(
              (f) => f.startsWith("agent-") && f.endsWith(".jsonl")
            ).length;
          } catch { /* no subagents dir */ }

          const taskDir = join(TASKS_DIR, sessionId);
          let taskCount = 0;
          try {
            const tasks = await readdir(taskDir);
            taskCount = tasks.length;
          } catch { /* no tasks dir */ }

          const conv = {
            sessionId,
            projectPath: entry.name,
            projectName: projectDirToDisplayName(entry.name),
            threadType: "main",
            firstMessage: summary.firstMessage,
            timestamp: summary.timestamp,
            messageCount: summary.messageCount,
            model: summary.model,
            totalInputTokens: summary.totalInputTokens,
            totalOutputTokens: summary.totalOutputTokens,
            totalCacheCreationTokens: summary.totalCacheCreationTokens,
            totalCacheReadTokens: summary.totalCacheReadTokens,
            toolUseCount: summary.toolUseCount,
            failedToolCallCount: summary.failedToolCallCount,
            toolBreakdown: summary.toolBreakdown,
            subagentCount,
            subagentTypeBreakdown: summary.subagentTypeBreakdown,
            taskCount,
            gitBranch: summary.gitBranch,
            speed: summary.speed,
            _summaryCacheVersion: 2,
          } as ConversationSummary & { _summaryCacheVersion: number };

          await summaryCache.set(filePath, conv);
          // Apply timestamp cutoff after parsing
          if (cutoffMs && conv.timestamp && conv.timestamp < cutoffMs) continue;
          if (dayScope === "today" && conv.timestamp < todayStartMs) continue;
          if (dayScope === "beforeToday" && conv.timestamp >= todayStartMs) continue;
          conversations.push(conv);
        } catch {
          // Skip files that can't be parsed
        }
      }
    }
  } catch {
    // Return empty if projects dir doesn't exist
  }

  // Merge Codex conversations (skip if filtering to a specific Claude project)
  if (!projectFilter || projectFilter.startsWith("codex:")) {
    try {
      const codexConvs = await listCodexConversations(days);
      const scopedCodexConvs = codexConvs.filter((conversation) => {
        if (dayScope === "today") {
          return conversation.timestamp >= todayStartMs;
        }
        if (dayScope === "beforeToday") {
          return conversation.timestamp < todayStartMs;
        }
        return true;
      });
      // If filtering by a codex project, apply the filter
      if (projectFilter) {
        conversations.push(
          ...scopedCodexConvs.filter((c) => c.projectPath === projectFilter)
        );
      } else {
        conversations.push(...scopedCodexConvs);
      }
    } catch {
      // Codex data not available — that's fine
    }
  }

  return conversations.sort((a, b) => b.timestamp - a.timestamp);
}

export async function listLegacyConversations(
  projectFilter?: string,
  days?: number
): Promise<ConversationSummary[]> {
  const [historicalConversations, liveConversations] = await Promise.all([
    Promise.resolve(
      historicalConversationStore.listConversationSummaries(projectFilter, days)
    ),
    listRawConversations(projectFilter, days, { dayScope: "today" }),
  ]);

  return [...historicalConversations, ...liveConversations].sort(
    (a, b) => b.timestamp - a.timestamp
  );
}

export const listConversations = listLegacyConversations;

/**
 * Discover subagent files for a session and extract references from parent events.
 */
async function discoverSubagents(
  projectPath: string,
  sessionId: string,
  events: import("./types").RawEvent[]
): Promise<SubagentInfo[]> {
  const subagentsDir = join(
    PROJECTS_DIR,
    projectPath,
    sessionId,
    "subagents"
  );

  // Find subagent files on disk
  const existingFiles = new Set<string>();
  try {
    const files = await readdir(subagentsDir);
    for (const f of files) {
      if (f.startsWith("agent-") && f.endsWith(".jsonl")) {
        existingFiles.add(f.replace("agent-", "").replace(".jsonl", ""));
      }
    }
  } catch {
    // No subagents directory
  }

  // Extract subagent references from parent conversation events
  const agentMap = new Map<
    string,
    { description?: string; subagentType?: string }
  >();

  for (const event of events) {
    // Look for Task tool_use blocks to get description/type
    if (event.type === "assistant" && event.message?.content) {
      const content = event.message.content;
      if (Array.isArray(content)) {
        for (const block of content) {
          if (
            typeof block === "object" &&
            block.type === "tool_use" &&
            block.name === "Task"
          ) {
            const input = block.input as Record<string, unknown>;
            // Store temporarily keyed by tool_use id
            agentMap.set(block.id, {
              description: input.description as string | undefined,
              subagentType: input.subagent_type as string | undefined,
            });
          }
        }
      }
    }

    // Look for tool results that contain agentId
    if (event.type === "user" && event.toolUseResult) {
      const result = event.toolUseResult;
      if (result && typeof result === "object" && "agentId" in result) {
        const agentId = (result as { agentId: string }).agentId;
        // Find the matching tool_use by tool_use_id from the tool_result content
        const content = event.message?.content;
        if (Array.isArray(content)) {
          for (const block of content) {
            if (typeof block === "object" && block.type === "tool_result") {
              const meta = agentMap.get(block.tool_use_id);
              if (meta) {
                agentMap.set(agentId, meta);
                agentMap.delete(block.tool_use_id);
              } else {
                agentMap.set(agentId, {
                  description: (result as { description?: string }).description,
                });
              }
            }
          }
        }
      }
    }
  }

  // Merge disk files with extracted metadata
  const allAgentIds = new Set([...existingFiles, ...agentMap.keys()]);
  const subagents: SubagentInfo[] = [];
  for (const agentId of allAgentIds) {
    const isKnownFile = existingFiles.has(agentId);
    const isLikelyAgentId =
      isKnownFile || /^[a-z][a-z0-9_-]{5,}$/i.test(agentId);
    if (!isLikelyAgentId) continue;
    const meta = agentMap.get(agentId);
    subagents.push({
      agentId,
      description: meta?.description,
      subagentType: meta?.subagentType,
      hasFile: existingFiles.has(agentId),
      projectPath,
      sessionId,
    });
  }

  return subagents;
}

export async function getRawConversation(
  projectPath: string,
  sessionId: string
): Promise<ProcessedConversation | null> {
  if (projectPath.startsWith("codex:")) {
    return getCodexConversation(sessionId);
  }

  const filePath = join(PROJECTS_DIR, projectPath, `${sessionId}.jsonl`);

  const cached = await conversationCache.get(filePath);
  if (cached) return cached as ProcessedConversation;

  try {
    const events = await parseJsonlFile(filePath);
    const processed = processConversation(events, sessionId, projectPath);
    processed.plans = processed.plans.map((plan) => ({
      ...plan,
      sourcePath: filePath,
      model: plan.model ?? processed.model,
    }));
    processed.subagents = await discoverSubagents(
      projectPath,
      sessionId,
      events
    );
    await conversationCache.set(filePath, processed);
    return processed;
  } catch {
    return null;
  }
}

export async function getConversation(
  projectPath: string,
  sessionId: string
): Promise<ProcessedConversation | null> {
  const historicalConversation = historicalConversationStore.getConversation(
    projectPath,
    sessionId
  );
  if (historicalConversation) {
    return historicalConversation;
  }

  return getRawConversation(projectPath, sessionId);
}

export async function getSubagentConversation(
  projectPath: string,
  sessionId: string,
  agentId: string
): Promise<ProcessedConversation | null> {
  if (projectPath.startsWith("codex:")) {
    const conversation = await getCodexConversation(agentId);
    if (!conversation) return null;
    return conversation;
  }

  const filePath = join(
    PROJECTS_DIR,
    projectPath,
    sessionId,
    "subagents",
    `agent-${agentId}.jsonl`
  );

  const cached = await conversationCache.get(filePath);
  if (cached) return cached as ProcessedConversation;

  try {
    const events = await parseJsonlFile(filePath);
    const processed = processConversation(events, agentId, projectPath);
    processed.subagents = await discoverSubagents(
      projectPath,
      agentId,
      events
    );
    await conversationCache.set(filePath, processed);
    return processed;
  } catch {
    return null;
  }
}

export async function listPlans(): Promise<PlanSummary[]> {
  const [claudePlans, codexPlans, filePlans] = await Promise.all([
    listClaudeSessionPlans(),
    listCodexPlans(),
    listFilePlans(),
  ]);

  return [...claudePlans, ...codexPlans, ...filePlans].sort(
    (a, b) => b.timestamp - a.timestamp || a.title.localeCompare(b.title)
  );
}

export async function getPlan(id: string): Promise<PlanDetail | null> {
  const source = decodePlanId(id);
  if (!source) return null;

  if (source.kind === "claude-session") {
    return getClaudeSessionPlan(id);
  }

  if (source.kind === "codex-session") {
    return getCodexPlan(id);
  }

  try {
    const filePath = join(PLANS_DIR, `${source.slug}.md`);
    const content = await readFile(filePath, "utf-8");
    const fileStat = await stat(filePath).catch(() => null);
    const metadata = summarizePlanContent(content, source.slug);
    return {
      id,
      slug: metadata.slug,
      title: metadata.title,
      content,
      provider: "claude",
      timestamp: fileStat?.mtimeMs ?? 0,
      sourcePath: filePath,
    };
  } catch {
    return null;
  }
}

export async function getHistory(limit = 100): Promise<HistoryEntry[]> {
  const entries: HistoryEntry[] = [];

  // Claude history
  try {
    const content = await readFile(HISTORY_FILE, "utf-8");
    const lines = content.split("\n").filter((l) => l.trim());
    for (const line of lines) {
      try {
        entries.push(JSON.parse(line));
      } catch {
        continue;
      }
    }
  } catch {
    // No Claude history
  }

  // Codex history
  try {
    const codexEntries = await getCodexHistory(limit);
    entries.push(...codexEntries);
  } catch {
    // No Codex history
  }

  return entries
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, limit);
}

export async function getRawTasksForSession(
  sessionId: string
): Promise<unknown[]> {
  const taskDir = join(TASKS_DIR, sessionId);
  try {
    const entries = await readdir(taskDir, { withFileTypes: true });
    const tasks: unknown[] = [];

    for (const entry of entries) {
      if (!entry.isFile()) continue;
      try {
        const content = await readFile(join(taskDir, entry.name), "utf-8");
        tasks.push(JSON.parse(content));
      } catch {
        continue;
      }
    }

    return tasks;
  } catch {
    return [];
  }
}

export async function getTasksForSession(
  sessionId: string
): Promise<unknown[]> {
  const historicalTasks = historicalConversationStore.getTasksForSession(
    sessionId
  );
  if (historicalTasks) {
    return historicalTasks;
  }

  return getRawTasksForSession(sessionId);
}

export async function getLegacyAnalytics(
  days?: number,
  provider?: string
): Promise<AnalyticsData> {
  let conversations = await listLegacyConversations(undefined, days);

  if (provider === "claude") {
    conversations = conversations.filter((c) => !c.projectPath.startsWith("codex:"));
  } else if (provider === "codex") {
    conversations = conversations.filter((c) => c.projectPath.startsWith("codex:"));
  }

  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let totalCacheCreationTokens = 0;
  let totalCacheReadTokens = 0;
  let totalReasoningTokens = 0;
  let totalToolCalls = 0;
  let totalFailedToolCalls = 0;
  const modelBreakdown: Record<string, number> = {};
  const toolBreakdown: Record<string, number> = {};
  const subagentTypeBreakdown: Record<string, number> = {};
  const modelBreakdownByProvider: Record<string, ProviderBreakdown> = {};
  const toolBreakdownByProvider: Record<string, ProviderBreakdown> = {};
  const subagentTypeBreakdownByProvider: Record<string, ProviderBreakdown> = {};
  const dailyMap = new Map<string, DailyUsage>();
  const costBreakdownByProvider: Record<string, AnalyticsCostBreakdown> = {};
  const costBreakdownByModel: Record<string, AnalyticsCostBreakdown> = {};
  const timeSeriesMaps: Record<TimeSeriesKey, Map<string, AnalyticsTimeSeriesPoint>> = {
    hourly: new Map(),
    daily: new Map(),
    weekly: new Map(),
    monthly: new Map(),
  };
  let totalInputCost = 0;
  let totalOutputCost = 0;
  let totalCacheWriteCost = 0;
  let totalCacheReadCost = 0;
  let longContextPremium = 0;
  let longContextConversations = 0;

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
  ) {
    target.inputCost += source.inputCost;
    target.outputCost += source.outputCost;
    target.cacheWriteCost += source.cacheWriteCost;
    target.cacheReadCost += source.cacheReadCost;
    target.longContextPremium += source.longContextPremium;
    target.longContextConversations += source.longContextConversations;
    target.totalCost += source.totalCost;
  }

  function getProviderKey(conv: ConversationSummary): keyof ProviderBreakdown {
    return conv.projectPath.startsWith("codex:") ? "codex" : "claude";
  }

  function incrementProviderBreakdown(
    map: Record<string, ProviderBreakdown>,
    key: string,
    providerKey: keyof ProviderBreakdown,
    count: number
  ) {
    const existing = map[key] || { claude: 0, codex: 0 };
    existing[providerKey] += count;
    map[key] = existing;
  }

  for (const conv of conversations) {
    const providerKey = getProviderKey(conv);
    const reasoningTokens = conv.totalReasoningTokens || 0;
    const usage = {
      inputTokens: conv.totalInputTokens,
      outputTokens: conv.totalOutputTokens,
      cacheWriteTokens: conv.totalCacheCreationTokens,
      cacheReadTokens: conv.totalCacheReadTokens,
    };
    const baseCost = calculateCost(usage, conv.model);
    let convLongContextPremium = 0;
    let convLongContextConversations = 0;
    if (conv.totalInputTokens > 200_000 && hasLongContextPremium(conv.model)) {
      convLongContextPremium =
        baseCost.inputCost +
        baseCost.outputCost * 0.5 +
        baseCost.cacheWriteCost +
        baseCost.cacheReadCost;
      convLongContextConversations = 1;
    }
    const convCostBreakdown: AnalyticsCostBreakdown = {
      inputCost: baseCost.inputCost,
      outputCost: baseCost.outputCost,
      cacheWriteCost: baseCost.cacheWriteCost,
      cacheReadCost: baseCost.cacheReadCost,
      longContextPremium: convLongContextPremium,
      longContextConversations: convLongContextConversations,
      totalCost:
        baseCost.inputCost +
        baseCost.outputCost +
        baseCost.cacheWriteCost +
        baseCost.cacheReadCost +
        convLongContextPremium,
    };
    const totalTokensForConv =
      conv.totalInputTokens +
      conv.totalOutputTokens +
      conv.totalCacheCreationTokens +
      conv.totalCacheReadTokens +
      reasoningTokens;

    totalInputTokens += conv.totalInputTokens;
    totalOutputTokens += conv.totalOutputTokens;
    totalCacheCreationTokens += conv.totalCacheCreationTokens;
    totalCacheReadTokens += conv.totalCacheReadTokens;
    totalReasoningTokens += reasoningTokens;
    totalToolCalls += conv.toolUseCount;
    totalFailedToolCalls += conv.failedToolCallCount || 0;
    totalInputCost += baseCost.inputCost;
    totalOutputCost += baseCost.outputCost;
    totalCacheWriteCost += baseCost.cacheWriteCost;
    totalCacheReadCost += baseCost.cacheReadCost;
    longContextPremium += convLongContextPremium;
    longContextConversations += convLongContextConversations;

    const providerCostBreakdown =
      costBreakdownByProvider[providerKey] || emptyCostBreakdown();
    const modelKey = conv.model || "unknown";
    const modelCostBreakdown =
      costBreakdownByModel[modelKey] || emptyCostBreakdown();
    addCostBreakdown(providerCostBreakdown, convCostBreakdown);
    addCostBreakdown(modelCostBreakdown, convCostBreakdown);
    costBreakdownByProvider[providerKey] = providerCostBreakdown;
    costBreakdownByModel[modelKey] = modelCostBreakdown;

    if (conv.model) {
      modelBreakdown[conv.model] = (modelBreakdown[conv.model] || 0) + 1;
      incrementProviderBreakdown(modelBreakdownByProvider, conv.model, providerKey, 1);
    }

    // Aggregate tool breakdown
    if (conv.toolBreakdown) {
      for (const [toolName, count] of Object.entries(conv.toolBreakdown)) {
        toolBreakdown[toolName] = (toolBreakdown[toolName] || 0) + count;
        incrementProviderBreakdown(toolBreakdownByProvider, toolName, providerKey, count);
      }
    }

    // Aggregate sub-agent type breakdown
    if (conv.subagentTypeBreakdown) {
      for (const [agentType, count] of Object.entries(conv.subagentTypeBreakdown)) {
        subagentTypeBreakdown[agentType] = (subagentTypeBreakdown[agentType] || 0) + count;
        incrementProviderBreakdown(
          subagentTypeBreakdownByProvider,
          agentType,
          providerKey,
          count
        );
      }
    }

    // Daily aggregation
    if (conv.timestamp) {
      const date = new Date(conv.timestamp).toISOString().split("T")[0];
      const existing = dailyMap.get(date) || {
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
      existing.inputTokens += conv.totalInputTokens;
      existing.outputTokens += conv.totalOutputTokens;
      existing.cacheWriteTokens += conv.totalCacheCreationTokens;
      existing.cacheReadTokens += conv.totalCacheReadTokens;
      existing.conversations += 1;
      existing.subagents += conv.subagentCount;
      if (providerKey === "claude") {
        existing.claudeInputTokens += conv.totalInputTokens;
        existing.claudeOutputTokens += conv.totalOutputTokens;
        existing.claudeCacheWriteTokens += conv.totalCacheCreationTokens;
        existing.claudeCacheReadTokens += conv.totalCacheReadTokens;
        existing.claudeConversations += 1;
        existing.claudeSubagents += conv.subagentCount;
      } else {
        existing.codexInputTokens += conv.totalInputTokens;
        existing.codexOutputTokens += conv.totalOutputTokens;
        existing.codexCacheWriteTokens += conv.totalCacheCreationTokens;
        existing.codexCacheReadTokens += conv.totalCacheReadTokens;
        existing.codexConversations += 1;
        existing.codexSubagents += conv.subagentCount;
      }
      dailyMap.set(date, existing);

      for (const timeSeriesKey of TIME_SERIES_KEYS) {
        const bucketStart = getBucketStart(conv.timestamp, timeSeriesKey);
        const bucketId = bucketStart.toISOString();
        const existingBucket =
          timeSeriesMaps[timeSeriesKey].get(bucketId) ||
          createEmptyTimeSeriesPoint(bucketStart, timeSeriesKey);

        existingBucket.estimatedCost += convCostBreakdown.totalCost;
        existingBucket.inputTokens += conv.totalInputTokens;
        existingBucket.outputTokens += conv.totalOutputTokens;
        existingBucket.cacheWriteTokens += conv.totalCacheCreationTokens;
        existingBucket.cacheReadTokens += conv.totalCacheReadTokens;
        existingBucket.reasoningTokens += reasoningTokens;
        existingBucket.totalTokens += totalTokensForConv;
        existingBucket.conversations += 1;
        existingBucket.toolCalls += conv.toolUseCount;
        existingBucket.failedToolCalls += conv.failedToolCallCount || 0;
        existingBucket.subagents += conv.subagentCount;

        if (providerKey === "claude") {
          existingBucket.claudeEstimatedCost += convCostBreakdown.totalCost;
          existingBucket.claudeInputTokens += conv.totalInputTokens;
          existingBucket.claudeOutputTokens += conv.totalOutputTokens;
          existingBucket.claudeCacheWriteTokens += conv.totalCacheCreationTokens;
          existingBucket.claudeCacheReadTokens += conv.totalCacheReadTokens;
          existingBucket.claudeReasoningTokens += reasoningTokens;
          existingBucket.claudeTotalTokens += totalTokensForConv;
          existingBucket.claudeConversations += 1;
          existingBucket.claudeToolCalls += conv.toolUseCount;
          existingBucket.claudeFailedToolCalls += conv.failedToolCallCount || 0;
          existingBucket.claudeSubagents += conv.subagentCount;
        } else {
          existingBucket.codexEstimatedCost += convCostBreakdown.totalCost;
          existingBucket.codexInputTokens += conv.totalInputTokens;
          existingBucket.codexOutputTokens += conv.totalOutputTokens;
          existingBucket.codexCacheWriteTokens += conv.totalCacheCreationTokens;
          existingBucket.codexCacheReadTokens += conv.totalCacheReadTokens;
          existingBucket.codexReasoningTokens += reasoningTokens;
          existingBucket.codexTotalTokens += totalTokensForConv;
          existingBucket.codexConversations += 1;
          existingBucket.codexToolCalls += conv.toolUseCount;
          existingBucket.codexFailedToolCalls += conv.failedToolCallCount || 0;
          existingBucket.codexSubagents += conv.subagentCount;
        }

        timeSeriesMaps[timeSeriesKey].set(bucketId, existingBucket);
      }
    }
  }

  const estimatedCost =
    totalInputCost + totalOutputCost + totalCacheWriteCost + totalCacheReadCost + longContextPremium;

  const costBreakdown = {
    inputCost: totalInputCost,
    outputCost: totalOutputCost,
    cacheWriteCost: totalCacheWriteCost,
    cacheReadCost: totalCacheReadCost,
    longContextPremium,
    longContextConversations,
    totalCost: estimatedCost,
  };

  const windowEnd = Date.now();
  const earliestTimestamp =
    conversations.length > 0
      ? Math.min(...conversations.map((conv) => conv.timestamp || windowEnd))
      : windowEnd;
  const windowStart = days
    ? windowEnd - days * 24 * 60 * 60 * 1000
    : earliestTimestamp;
  const durationMs = Math.max(windowEnd - windowStart, 60 * 60 * 1000);
  const durationHours = Math.max(durationMs / (60 * 60 * 1000), 1);
  const durationDays = Math.max(durationMs / (24 * 60 * 60 * 1000), 1 / 24);
  const totalTokens =
    totalInputTokens +
    totalOutputTokens +
    totalCacheCreationTokens +
    totalCacheReadTokens +
    totalReasoningTokens;
  const rates: AnalyticsRates = {
    spend: buildRateValue(estimatedCost, durationHours, durationDays),
    totalTokens: buildRateValue(totalTokens, durationHours, durationDays),
    inputTokens: buildRateValue(totalInputTokens, durationHours, durationDays),
    outputTokens: buildRateValue(totalOutputTokens, durationHours, durationDays),
    cacheWriteTokens: buildRateValue(
      totalCacheCreationTokens,
      durationHours,
      durationDays
    ),
    cacheReadTokens: buildRateValue(
      totalCacheReadTokens,
      durationHours,
      durationDays
    ),
    reasoningTokens: buildRateValue(
      totalReasoningTokens,
      durationHours,
      durationDays
    ),
    conversations: buildRateValue(
      conversations.length,
      durationHours,
      durationDays
    ),
    toolCalls: buildRateValue(totalToolCalls, durationHours, durationDays),
    failedToolCalls: buildRateValue(
      totalFailedToolCalls,
      durationHours,
      durationDays
    ),
    subagents: buildRateValue(
      conversations.reduce((sum, conv) => sum + conv.subagentCount, 0),
      durationHours,
      durationDays
    ),
  };
  const timeSeries: AnalyticsTimeSeries = {
    hourly: materializeTimeSeries(timeSeriesMaps.hourly, "hourly").map(withToolErrorRates),
    daily: materializeTimeSeries(timeSeriesMaps.daily, "daily").map(withToolErrorRates),
    weekly: materializeTimeSeries(timeSeriesMaps.weekly, "weekly").map(withToolErrorRates),
    monthly: materializeTimeSeries(timeSeriesMaps.monthly, "monthly").map(withToolErrorRates),
  };

  return {
    totalConversations: conversations.length,
    totalInputTokens,
    totalOutputTokens,
    totalCacheCreationTokens,
    totalCacheReadTokens,
    totalReasoningTokens,
    totalToolCalls,
    totalFailedToolCalls,
    modelBreakdown,
    toolBreakdown,
    subagentTypeBreakdown,
    modelBreakdownByProvider,
    toolBreakdownByProvider,
    subagentTypeBreakdownByProvider,
    dailyUsage: Array.from(dailyMap.values()).sort((a, b) =>
      a.date.localeCompare(b.date)
    ),
    rates,
    timeSeries,
    estimatedCost,
    costBreakdown,
    costBreakdownByProvider,
    costBreakdownByModel,
  };
}

export const getAnalytics = getLegacyAnalytics;
