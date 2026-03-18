import { createReadStream } from "fs";
import { createInterface } from "readline";
import type { CodexRawLine } from "./codex-types";

/**
 * Stream-parse a Codex session JSONL file, yielding one parsed line at a time.
 */
export async function* streamCodexJsonl(
  filePath: string
): AsyncGenerator<CodexRawLine> {
  const fileStream = createReadStream(filePath, { encoding: "utf-8" });
  const rl = createInterface({ input: fileStream, crlfDelay: Infinity });

  for await (const line of rl) {
    if (!line.trim()) continue;
    try {
      yield JSON.parse(line) as CodexRawLine;
    } catch {
      continue;
    }
  }
}

/**
 * Parse and collect all lines from a Codex session JSONL file.
 */
export async function parseCodexJsonlFile(
  filePath: string
): Promise<CodexRawLine[]> {
  const lines: CodexRawLine[] = [];
  for await (const line of streamCodexJsonl(filePath)) {
    lines.push(line);
  }
  return lines;
}

/**
 * Extract summary metadata from a Codex session JSONL without full processing.
 */
export async function extractCodexSummary(filePath: string): Promise<{
  sessionId: string;
  firstMessage: string;
  messageCount: number;
  model: string;
  cwd: string;
  source: string;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCachedInputTokens: number;
  totalReasoningTokens: number;
  reasoningEffort?: string;
  toolUseCount: number;
  failedToolCallCount: number;
  toolBreakdown: Record<string, number>;
  subagentCount: number;
  subagentTypeBreakdown: Record<string, number>;
  parentThreadId?: string;
  agentRole?: string;
  agentNickname?: string;
  timestamp: number;
  endTimestamp: number;
}> {
  let sessionId = "";
  let firstMessage = "";
  let messageCount = 0;
  let model = "gpt-5";
  let cwd = "";
  let source = "";
  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let totalCachedInputTokens = 0;
  let totalReasoningTokens = 0;
  let reasoningEffort: string | undefined;
  let toolUseCount = 0;
  let failedToolCallCount = 0;
  const toolBreakdown: Record<string, number> = {};
  let subagentCount = 0;
  const subagentTypeBreakdown: Record<string, number> = {};
  let parentThreadId: string | undefined;
  let agentRole: string | undefined;
  let agentNickname: string | undefined;
  let timestamp = 0;
  let endTimestamp = 0;
  const pendingSpawnCalls = new Map<
    string,
    { subagentType?: string }
  >();

  // Track the last seen total token usage to compute final totals
  let lastTotalUsage: {
    input_tokens: number;
    cached_input_tokens: number;
    output_tokens: number;
    reasoning_output_tokens: number;
  } | null = null;

  for await (const line of streamCodexJsonl(filePath)) {
    const ts = new Date(line.timestamp).getTime();
    if (!timestamp || ts < timestamp) timestamp = ts;
    if (ts > endTimestamp) endTimestamp = ts;

    if (line.type === "session_meta") {
      const p = line.payload as Record<string, unknown>;
      sessionId = (p.id as string) || "";
      cwd = (p.cwd as string) || "";
      const sourceValue = p.source;
      if (typeof sourceValue === "string") {
        source = sourceValue;
      } else if (sourceValue && typeof sourceValue === "object") {
        source = "subagent";
        const threadSpawn = (
          sourceValue as {
            subagent?: {
              thread_spawn?: { parent_thread_id?: string };
            };
          }
        ).subagent?.thread_spawn;
        parentThreadId = threadSpawn?.parent_thread_id;
      }
      if (typeof p.agent_role === "string" && p.agent_role.trim()) {
        agentRole = p.agent_role;
      }
      if (typeof p.agent_nickname === "string" && p.agent_nickname.trim()) {
        agentNickname = p.agent_nickname;
      }
    }

    if (line.type === "turn_context") {
      const p = line.payload as Record<string, unknown>;
      if (typeof p.model === "string" && p.model.trim()) {
        model = p.model;
      }
      if (typeof p.reasoning_effort === "string" && p.reasoning_effort.trim()) {
        reasoningEffort = p.reasoning_effort;
      }
    }

    if (line.type === "response_item") {
      const p = line.payload as Record<string, unknown>;

      if (p.type === "message") {
        const role = p.role as string;
        if (role === "user") {
          messageCount++;
          if (!firstMessage) {
            const content = p.content as Array<{ type: string; text: string }>;
            if (Array.isArray(content)) {
              const textBlock = content.find(
                (b) => b.type === "input_text" && !b.text.startsWith("<")
              );
              if (textBlock) {
                firstMessage = textBlock.text.slice(0, 200);
              }
            }
          }
        } else if (role === "assistant") {
          messageCount++;
        }
      }

      if (p.type === "function_call") {
        toolUseCount++;
        const name = (p.name as string) || "unknown";
        const displayName = codexToolDisplayName(name);
        toolBreakdown[displayName] = (toolBreakdown[displayName] || 0) + 1;
        if (name === "spawn_agent") {
          const args = parseCodexToolArguments(p.arguments);
          pendingSpawnCalls.set((p.call_id as string) || "", {
            subagentType: getSpawnAgentType(args),
          });
        }
      }

      if (p.type === "custom_tool_call") {
        toolUseCount++;
        const name = (p.name as string) || "unknown";
        const displayName = codexToolDisplayName(name);
        toolBreakdown[displayName] = (toolBreakdown[displayName] || 0) + 1;
      }

      if (p.type === "web_search_call") {
        toolUseCount++;
        const displayName = codexToolDisplayName("web_search_call");
        toolBreakdown[displayName] = (toolBreakdown[displayName] || 0) + 1;
      }

      if (p.type === "function_call_output") {
        const output = (p.output as string) || "";
        if (output.includes("Process exited with code")) {
          const exitMatch = output.match(/Process exited with code (\d+)/);
          if (exitMatch && exitMatch[1] !== "0") {
            failedToolCallCount++;
          }
        }
        const callId = (p.call_id as string) || "";
        const pendingSpawn = pendingSpawnCalls.get(callId);
        if (pendingSpawn) {
          const { agentId } = parseSpawnAgentOutput(p.output);
          if (agentId) {
            subagentCount++;
            const agentType = pendingSpawn.subagentType || "default";
            subagentTypeBreakdown[agentType] =
              (subagentTypeBreakdown[agentType] || 0) + 1;
          }
          pendingSpawnCalls.delete(callId);
        }
      }

      if (p.type === "custom_tool_call_output") {
        const rawOutput = (p.output as string) || "";
        if (rawOutput.includes('"exit_code":') && !rawOutput.includes('"exit_code":0')) {
          failedToolCallCount++;
        }
      }
    }

    if (line.type === "event_msg") {
      const p = line.payload as Record<string, unknown>;
      if (p.type === "token_count") {
        const info = p.info as {
          total_token_usage?: {
            input_tokens: number;
            cached_input_tokens: number;
            output_tokens: number;
            reasoning_output_tokens: number;
          };
        } | null;
        if (info?.total_token_usage) {
          lastTotalUsage = info.total_token_usage;
        }
      }
    }
  }

  // Use the final cumulative token_count event
  if (lastTotalUsage) {
    totalInputTokens = lastTotalUsage.input_tokens;
    totalOutputTokens = lastTotalUsage.output_tokens;
    totalCachedInputTokens = lastTotalUsage.cached_input_tokens;
    totalReasoningTokens = lastTotalUsage.reasoning_output_tokens;
  }

  return {
    sessionId,
    firstMessage,
    messageCount,
    model,
    cwd,
    source,
    totalInputTokens,
    totalOutputTokens,
    totalCachedInputTokens,
    totalReasoningTokens,
    reasoningEffort,
    toolUseCount,
    failedToolCallCount,
    toolBreakdown,
    subagentCount,
    subagentTypeBreakdown,
    parentThreadId,
    agentRole,
    agentNickname,
    timestamp,
    endTimestamp,
  };
}

/** Map Codex tool names to human-readable display names */
export function codexToolDisplayName(rawName: string): string {
  switch (rawName) {
    case "exec_command":
      return "Shell";
    case "apply_patch":
      return "Patch";
    case "spawn_agent":
      return "Spawn Agent";
    case "send_input":
      return "Send Input";
    case "wait":
      return "Wait";
    case "close_agent":
      return "Close Agent";
    case "web_search_call":
      return "Web Search";
    default:
      return rawName;
  }
}

export function parseCodexToolArguments(
  rawArguments: unknown
): Record<string, unknown> {
  if (typeof rawArguments !== "string") return {};
  try {
    const parsed = JSON.parse(rawArguments);
    return parsed && typeof parsed === "object"
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

export function getSpawnAgentType(
  args: Record<string, unknown>
): string | undefined {
  const rawAgentType = args.agent_type;
  return typeof rawAgentType === "string" && rawAgentType.trim()
    ? rawAgentType
    : undefined;
}

export function summarizeSpawnAgentMessage(
  args: Record<string, unknown>
): string | undefined {
  const rawMessage = args.message;
  if (typeof rawMessage !== "string") return undefined;

  const firstLine = rawMessage
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.length > 0);

  if (!firstLine) return undefined;
  return firstLine.length > 200 ? `${firstLine.slice(0, 197)}...` : firstLine;
}

export function parseSpawnAgentOutput(rawOutput: unknown): {
  agentId?: string;
  nickname?: string;
} {
  if (typeof rawOutput !== "string") return {};

  try {
    const parsed = JSON.parse(rawOutput) as {
      agent_id?: string;
      agentId?: string;
      id?: string;
      nickname?: string;
    };
    return {
      agentId: parsed.agent_id || parsed.agentId || parsed.id,
      nickname:
        typeof parsed.nickname === "string" ? parsed.nickname : undefined,
    };
  } catch {
    return {};
  }
}
