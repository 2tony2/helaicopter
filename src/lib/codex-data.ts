import { readdir, stat } from "fs/promises";
import { join } from "path";
import { CODEX_SESSIONS_DIR, CODEX_HISTORY_FILE, CODEX_DB_PATH } from "./constants";
import {
  extractCodexSummary,
  parseCodexJsonlFile,
  parseCodexToolArguments,
  parseSpawnAgentOutput,
  summarizeSpawnAgentMessage,
  getSpawnAgentType,
} from "./codex-jsonl-parser";
import {
  extractCodexPlans,
  processCodexConversation,
} from "./codex-conversation-processor";
import { summaryCache, conversationCache } from "./cache";
import type {
  ConversationSummary,
  ProcessedConversation,
  HistoryEntry,
  PlanDetail,
  PlanSummary,
} from "./types";
import Database from "better-sqlite3";
import { decodePlanId } from "./plan-utils";

/** Thread metadata from Codex SQLite database */
interface CodexThread {
  id: string;
  title: string | null;
  cwd: string | null;
  source: string | null;
  model_provider: string | null;
  tokens_used: number | null;
  git_sha: string | null;
  git_branch: string | null;
  git_origin_url: string | null;
  cli_version: string | null;
  first_user_message: string | null;
  created_at: number | null;
  updated_at: number | null;
  rollout_path: string | null;
  agent_role: string | null;
  agent_nickname: string | null;
}

interface CodexConversationSummaryCache extends ConversationSummary {
  _codexCacheVersion: 3;
  _codexParentThreadId?: string;
  _codexAgentRole?: string;
  _codexAgentNickname?: string;
}

interface CodexConversationCache extends ProcessedConversation {
  _codexCacheVersion: 3;
}

function parseThreadSource(source: string | null): { parentThreadId?: string } {
  if (!source || !source.trim().startsWith("{")) return {};

  try {
    const parsed = JSON.parse(source) as {
      subagent?: {
        thread_spawn?: {
          parent_thread_id?: string;
        };
      };
    };
    return {
      parentThreadId: parsed.subagent?.thread_spawn?.parent_thread_id,
    };
  } catch {
    return {};
  }
}

/** Get thread metadata from Codex SQLite DB for enrichment */
function getThreadMetadata(): Map<string, CodexThread> {
  const map = new Map<string, CodexThread>();
  try {
    const db = new Database(CODEX_DB_PATH, { readonly: true });
    const rows = db
      .prepare(
        `SELECT id, title, cwd, source, model_provider, tokens_used,
                git_sha, git_branch, git_origin_url, cli_version,
                first_user_message, created_at, updated_at, rollout_path,
                agent_role, agent_nickname
         FROM threads`
      )
      .all() as CodexThread[];
    db.close();
    for (const row of rows) {
      map.set(row.id, row);
    }
  } catch {
    // SQLite not available or table doesn't exist — proceed without enrichment
  }
  return map;
}

/**
 * Recursively find all .jsonl session files under ~/.codex/sessions/
 * Structure: sessions/YYYY/MM/DD/rollout-*.jsonl
 */
async function findSessionFiles(
  dir: string,
  cutoffMs: number
): Promise<{ filePath: string; sessionId: string }[]> {
  const results: { filePath: string; sessionId: string }[] = [];

  async function walk(currentDir: string) {
    let entries;
    try {
      entries = await readdir(currentDir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      const fullPath = join(currentDir, entry.name);
      if (entry.isDirectory()) {
        await walk(fullPath);
      } else if (entry.name.endsWith(".jsonl")) {
        // Fast mtime check
        if (cutoffMs) {
          try {
            const s = await stat(fullPath);
            if (s.mtimeMs < cutoffMs) continue;
          } catch {
            continue;
          }
        }

        // Extract session ID from filename
        // Format: rollout-2026-03-11T09-25-04-019cdbff-dbb7-71d0-baaf-c669c55af628.jsonl
        const match = entry.name.match(
          /([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$/i
        );
        if (match) {
          results.push({ filePath: fullPath, sessionId: match[1] });
        }
      }
    }
  }

  await walk(dir);
  return results;
}

/** Convert a Codex cwd to a project path similar to Claude's encoding */
function cwdToProjectPath(cwd: string): string {
  if (!cwd) return "codex-unknown";
  // Encode like Claude: /Users/tony/Code/foo → -Users-tony-Code-foo
  return cwd.replace(/\//g, "-");
}

/** Convert a Codex cwd to a display name */
function cwdToDisplayName(cwd: string): string {
  if (!cwd) return "Unknown";
  const segments = cwd.split("/").filter(Boolean);
  // Return last 2-3 meaningful segments
  const startIdx = segments.findIndex(
    (s, i) => i >= 2 && s !== "Documents" && s !== "Users"
  );
  return segments.slice(Math.max(startIdx, 0)).slice(-3).join("/");
}

function mergeSubagentTypeBreakdowns(
  preferred: Record<string, number>,
  fallback: Record<string, number>
): Record<string, number> {
  return Object.keys(preferred).length > 0 ? preferred : fallback;
}

async function discoverCodexSubagents(
  lines: import("./codex-types").CodexRawLine[],
  sessionId: string,
  projectPath: string,
  threadMeta: Map<string, CodexThread>
): Promise<ProcessedConversation["subagents"]> {
  const pendingSpawnCalls = new Map<
    string,
    { description?: string; subagentType?: string }
  >();
  const subagents = new Map<string, ProcessedConversation["subagents"][number]>();

  for (const line of lines) {
    if (line.type !== "response_item") continue;
    const payload = line.payload as Record<string, unknown>;

    if (payload.type === "function_call" && payload.name === "spawn_agent") {
      const args = parseCodexToolArguments(payload.arguments);
      pendingSpawnCalls.set((payload.call_id as string) || "", {
        description: summarizeSpawnAgentMessage(args),
        subagentType: getSpawnAgentType(args),
      });
      continue;
    }

    if (payload.type === "function_call_output") {
      const callId = (payload.call_id as string) || "";
      const pendingSpawn = pendingSpawnCalls.get(callId);
      if (!pendingSpawn) continue;

      const { agentId, nickname } = parseSpawnAgentOutput(payload.output);
      if (agentId) {
        const thread = threadMeta.get(agentId);
        subagents.set(agentId, {
          agentId,
          description: pendingSpawn.description,
          subagentType:
            thread?.agent_role || pendingSpawn.subagentType || undefined,
          nickname: thread?.agent_nickname || nickname || undefined,
          hasFile: threadMeta.has(agentId),
          projectPath,
          sessionId,
        });
      }

      pendingSpawnCalls.delete(callId);
    }
  }

  for (const [agentId, thread] of threadMeta.entries()) {
    const { parentThreadId } = parseThreadSource(thread.source);
    if (parentThreadId !== sessionId) continue;

    const existing = subagents.get(agentId);
    subagents.set(agentId, {
      agentId,
      description: existing?.description,
      subagentType: thread.agent_role || existing?.subagentType || undefined,
      nickname: thread.agent_nickname || existing?.nickname || undefined,
      hasFile: true,
      projectPath,
      sessionId,
    });
  }

  return Array.from(subagents.values()).sort((a, b) =>
    a.agentId.localeCompare(b.agentId)
  );
}

export async function listCodexConversations(
  days?: number
): Promise<ConversationSummary[]> {
  const cutoffMs = days ? Date.now() - days * 24 * 60 * 60 * 1000 : 0;
  const conversations: CodexConversationSummaryCache[] = [];

  const sessionFiles = await findSessionFiles(CODEX_SESSIONS_DIR, cutoffMs);
  const threadMeta = getThreadMetadata();

  for (const { filePath, sessionId } of sessionFiles) {
    // Check cache first
    const cached = await summaryCache.get(filePath);
    if (cached && (cached as { _codexCacheVersion?: number })._codexCacheVersion === 3) {
      const c = cached as CodexConversationSummaryCache;
      if (cutoffMs && c.timestamp && c.timestamp < cutoffMs) continue;
      conversations.push(c);
      continue;
    }

    try {
      const summary = await extractCodexSummary(filePath);

      // Enrich with SQLite metadata
      const thread = threadMeta.get(sessionId);
      const { parentThreadId } = parseThreadSource(thread?.source || null);
      const cwd = thread?.cwd || summary.cwd;
      const projectPath = "codex:" + cwdToProjectPath(cwd);
      const firstMessage = thread?.first_user_message || summary.firstMessage;

      const conv: CodexConversationSummaryCache = {
        sessionId,
        projectPath,
        projectName: cwdToDisplayName(cwd),
        firstMessage: firstMessage.slice(0, 200),
        timestamp: summary.timestamp,
        messageCount: summary.messageCount,
        model: summary.model,
        totalInputTokens: summary.totalInputTokens,
        totalOutputTokens: summary.totalOutputTokens,
        totalCacheCreationTokens: 0,
        totalCacheReadTokens: summary.totalCachedInputTokens,
        toolUseCount: summary.toolUseCount,
        toolBreakdown: summary.toolBreakdown,
        subagentCount: summary.subagentCount,
        subagentTypeBreakdown: summary.subagentTypeBreakdown,
        taskCount: 0,
        gitBranch: thread?.git_branch || undefined,
        reasoningEffort: summary.reasoningEffort,
        totalReasoningTokens: summary.totalReasoningTokens > 0 ? summary.totalReasoningTokens : undefined,
        _codexCacheVersion: 3,
        _codexParentThreadId: parentThreadId || summary.parentThreadId,
        _codexAgentRole: thread?.agent_role || summary.agentRole,
        _codexAgentNickname: thread?.agent_nickname || summary.agentNickname,
      };

      await summaryCache.set(filePath, conv);
      if (cutoffMs && conv.timestamp && conv.timestamp < cutoffMs) continue;
      conversations.push(conv);
    } catch {
      // Skip unparseable files
    }
  }

  const childGroups = new Map<
    string,
    { count: number; typeBreakdown: Record<string, number> }
  >();

  for (const conv of conversations) {
    const parentThreadId = conv._codexParentThreadId;
    if (!parentThreadId) continue;

    const existing = childGroups.get(parentThreadId) || {
      count: 0,
      typeBreakdown: {},
    };
    existing.count += 1;
    const agentType = conv._codexAgentRole || "default";
    existing.typeBreakdown[agentType] =
      (existing.typeBreakdown[agentType] || 0) + 1;
    childGroups.set(parentThreadId, existing);
  }

  return conversations
    .filter((conv) => !conv._codexParentThreadId)
    .map((conv) => {
      const childGroup = childGroups.get(conv.sessionId);
      if (!childGroup) return conv;

      return {
        ...conv,
        subagentCount: childGroup.count,
        subagentTypeBreakdown: mergeSubagentTypeBreakdowns(
          childGroup.typeBreakdown,
          conv.subagentTypeBreakdown
        ),
      };
    })
    .sort((a, b) => b.timestamp - a.timestamp);
}

export async function getCodexConversation(
  sessionId: string
): Promise<ProcessedConversation | null> {
  // Find the session file
  const sessionFiles = await findSessionFiles(CODEX_SESSIONS_DIR, 0);
  const match = sessionFiles.find((f) => f.sessionId === sessionId);
  if (!match) return null;

  const cached = await conversationCache.get(match.filePath);
  if (cached && (cached as { _codexCacheVersion?: number })._codexCacheVersion === 3) {
    return cached as ProcessedConversation;
  }

  try {
    const lines = await parseCodexJsonlFile(match.filePath);
    const threadMeta = getThreadMetadata();

    // Determine project path from session_meta or SQLite
    let projectPath = "codex:unknown";
    const metaLine = lines.find((l) => l.type === "session_meta");
    if (metaLine) {
      const p = metaLine.payload as Record<string, unknown>;
      const cwd = p.cwd as string;
      if (cwd) projectPath = "codex:" + cwdToProjectPath(cwd);
    }

    // Enrich with SQLite git branch
    const thread = threadMeta.get(sessionId);
    if (thread?.cwd) {
      projectPath = "codex:" + cwdToProjectPath(thread.cwd);
    }

    const processed: CodexConversationCache = {
      ...processCodexConversation(
      lines,
      sessionId,
      projectPath
      ),
      _codexCacheVersion: 3,
    };
    if (thread?.git_branch) {
      processed.gitBranch = thread.git_branch;
    }
    processed.subagents = await discoverCodexSubagents(
      lines,
      sessionId,
      projectPath,
      threadMeta
    );

    await conversationCache.set(match.filePath, processed);
    return processed;
  } catch {
    return null;
  }
}

export async function listCodexPlans(): Promise<PlanSummary[]> {
  const sessionFiles = await findSessionFiles(CODEX_SESSIONS_DIR, 0);
  const plans: PlanSummary[] = [];

  for (const { filePath, sessionId } of sessionFiles) {
    try {
      const lines = await parseCodexJsonlFile(filePath);

      let projectPath = "codex:unknown";
      const metaLine = lines.find((line) => line.type === "session_meta");
      if (metaLine) {
        const payload = metaLine.payload as Record<string, unknown>;
        if (typeof payload.cwd === "string" && payload.cwd.trim()) {
          projectPath = `codex:${cwdToProjectPath(payload.cwd)}`;
        }
      }

      plans.push(
        ...extractCodexPlans(lines, sessionId, projectPath).map((plan) => ({
          id: plan.id,
          slug: plan.slug,
          title: plan.title,
          preview: plan.preview,
          provider: plan.provider,
          timestamp: plan.timestamp,
          sessionId: plan.sessionId,
          projectPath: plan.projectPath,
        }))
      );
    } catch {
      // Skip unparseable files.
    }
  }

  return plans.sort((a, b) => b.timestamp - a.timestamp);
}

export async function getCodexPlan(id: string): Promise<PlanDetail | null> {
  const source = decodePlanId(id);
  if (!source || source.kind !== "codex-session") return null;

  const sessionFiles = await findSessionFiles(CODEX_SESSIONS_DIR, 0);
  const match = sessionFiles.find((file) => file.sessionId === source.sessionId);
  if (!match) return null;

  try {
    const lines = await parseCodexJsonlFile(match.filePath);

    let projectPath = "codex:unknown";
    const metaLine = lines.find((line) => line.type === "session_meta");
    if (metaLine) {
      const payload = metaLine.payload as Record<string, unknown>;
      if (typeof payload.cwd === "string" && payload.cwd.trim()) {
        projectPath = `codex:${cwdToProjectPath(payload.cwd)}`;
      }
    }

    const plan = extractCodexPlans(lines, source.sessionId, projectPath).find(
      (entry) => entry.id === id
    );
    if (!plan) return null;

    return {
      id: plan.id,
      slug: plan.slug,
      title: plan.title,
      content: plan.content,
      provider: plan.provider,
      timestamp: plan.timestamp,
      sessionId: plan.sessionId,
      projectPath: plan.projectPath,
    };
  } catch {
    return null;
  }
}

export async function getCodexHistory(limit = 100): Promise<HistoryEntry[]> {
  try {
    const { readFile } = await import("fs/promises");
    const content = await readFile(CODEX_HISTORY_FILE, "utf-8");
    const lines = content.split("\n").filter((l) => l.trim());
    const entries: HistoryEntry[] = [];

    for (const line of lines) {
      try {
        const parsed = JSON.parse(line) as {
          session_id?: string;
          ts?: number;
          text?: string;
        };
        entries.push({
          display: parsed.text || "",
          timestamp: (parsed.ts || 0) * 1000, // Codex uses seconds, we use ms
          project: parsed.session_id,
        });
      } catch {
        continue;
      }
    }

    return entries
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, limit);
  } catch {
    return [];
  }
}
