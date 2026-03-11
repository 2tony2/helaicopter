import { createReadStream } from "fs";
import { createInterface } from "readline";
import type { RawEvent } from "./types";

/** Normalize a timestamp (ISO string or epoch ms) to epoch ms number */
function toEpochMs(ts: unknown): number {
  if (typeof ts === "number") return ts;
  if (typeof ts === "string") return new Date(ts).getTime();
  return 0;
}

/**
 * Stream-parse a JSONL file, yielding one parsed object per line.
 * Handles files up to 200MB+ without loading into memory.
 */
export async function* streamJsonl(filePath: string): AsyncGenerator<RawEvent> {
  const fileStream = createReadStream(filePath, { encoding: "utf-8" });
  const rl = createInterface({ input: fileStream, crlfDelay: Infinity });

  for await (const line of rl) {
    if (!line.trim()) continue;
    try {
      yield JSON.parse(line) as RawEvent;
    } catch {
      // Skip malformed lines
      continue;
    }
  }
}

/**
 * Stream-parse and collect all events from a JSONL file.
 * For smaller files where you need all events at once.
 */
export async function parseJsonlFile(filePath: string): Promise<RawEvent[]> {
  const events: RawEvent[] = [];
  for await (const event of streamJsonl(filePath)) {
    events.push(event);
  }
  return events;
}

/**
 * Extract just the summary metadata from a conversation JSONL file.
 * Streams through only enough to get: first user message, message count, model, tokens.
 * Much faster than full parsing for list views.
 */
export async function extractConversationSummary(filePath: string): Promise<{
  firstMessage: string;
  messageCount: number;
  model?: string;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheCreationTokens: number;
  totalCacheReadTokens: number;
  toolUseCount: number;
  toolBreakdown: Record<string, number>;
  subagentTypeBreakdown: Record<string, number>;
  timestamp: number;
  endTimestamp: number;
  gitBranch?: string;
  speed?: string;
}> {
  let firstMessage = "";
  let messageCount = 0;
  let model: string | undefined;
  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let totalCacheCreationTokens = 0;
  let totalCacheReadTokens = 0;
  let toolUseCount = 0;
  const toolBreakdown: Record<string, number> = {};
  const subagentTypeBreakdown: Record<string, number> = {};
  let timestamp = 0;
  let endTimestamp = 0;
  let gitBranch: string | undefined;
  let speed: string | undefined;

  for await (const event of streamJsonl(filePath)) {
    if (event.type === "file-history-snapshot") continue;

    if (event.timestamp) {
      const ts = toEpochMs(event.timestamp);
      if (!timestamp || ts < timestamp) timestamp = ts;
      if (ts > endTimestamp) endTimestamp = ts;
    }

    if (!gitBranch && event.gitBranch) {
      gitBranch = event.gitBranch;
    }

    if (event.type === "user" && event.message?.role === "user") {
      messageCount++;
      if (!firstMessage) {
        const content = event.message.content;
        if (typeof content === "string") {
          firstMessage = content.slice(0, 200);
        } else if (Array.isArray(content)) {
          const textBlock = content.find(
            (b) => typeof b === "object" && b.type === "text"
          );
          if (textBlock && "text" in textBlock) {
            firstMessage = textBlock.text.slice(0, 200);
          }
        }
      }
    }

    if (event.type === "assistant" && event.message) {
      messageCount++;
      if (!model && event.message.model) {
        model = event.message.model;
      }

      const usage = event.message.usage;
      if (usage) {
        totalInputTokens += usage.input_tokens || 0;
        totalOutputTokens += usage.output_tokens || 0;
        totalCacheCreationTokens += usage.cache_creation_input_tokens || 0;
        totalCacheReadTokens += usage.cache_read_input_tokens || 0;
        if (!speed && usage.speed) {
          speed = usage.speed;
        }
      }

      const content = event.message.content;
      if (Array.isArray(content)) {
        for (const block of content) {
          if (typeof block === "object" && block.type === "tool_use") {
            toolUseCount++;
            const name = (block as { name?: string }).name;
            if (name) {
              toolBreakdown[name] = (toolBreakdown[name] || 0) + 1;
            }
            // Track sub-agent types from Task tool calls
            if (name === "Task") {
              const input = (block as { input?: Record<string, unknown> }).input;
              const agentType = (input?.subagent_type as string) || "unknown";
              subagentTypeBreakdown[agentType] = (subagentTypeBreakdown[agentType] || 0) + 1;
            }
          }
        }
      }
    }
  }

  return {
    firstMessage,
    messageCount,
    model,
    totalInputTokens,
    totalOutputTokens,
    totalCacheCreationTokens,
    totalCacheReadTokens,
    toolUseCount,
    toolBreakdown,
    subagentTypeBreakdown,
    timestamp,
    endTimestamp,
    gitBranch,
    speed,
  };
}
