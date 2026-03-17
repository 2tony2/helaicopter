import type {
  RawEvent,
  ProcessedConversation,
  ProcessedMessage,
  DisplayBlock,
  DisplayTextBlock,
  DisplayThinkingBlock,
  DisplayToolCallBlock,
  TokenUsage,
  ToolResultBlock,
  ContextBucket,
  ContextStep,
  ContextAnalytics,
  ConversationPlan,
} from "./types";
import { TOOL_RESULT_MAX_LENGTH } from "./constants";
import {
  encodePlanId,
  summarizePlanContent,
  toEpochMs,
} from "./plan-utils";

export function extractClaudePlans(
  events: RawEvent[],
  sessionId: string,
  projectPath: string
): ConversationPlan[] {
  const plans: ConversationPlan[] = [];
  let latestModel: string | undefined;

  for (const event of events) {
    if (event.type === "assistant" && typeof event.message?.model === "string") {
      latestModel = event.message.model;
    }

    if (typeof event.planContent !== "string" || !event.planContent.trim()) {
      continue;
    }

    const metadata = summarizePlanContent(
      event.planContent,
      event.slug || sessionId
    );

    plans.push({
      id: encodePlanId({
        kind: "claude-session",
        projectPath,
        sessionId,
        eventId: event.uuid,
      }),
      provider: "claude",
      timestamp: toEpochMs(event.timestamp),
      sessionId,
      projectPath,
      model: latestModel,
      content: event.planContent,
      ...metadata,
    });
  }

  return plans.sort((a, b) => b.timestamp - a.timestamp);
}

function usageTotal(u: TokenUsage | undefined) {
  if (!u) return 0;
  return (
    (u.input_tokens || 0) +
    (u.output_tokens || 0) +
    (u.cache_creation_input_tokens || 0) +
    (u.cache_read_input_tokens || 0)
  );
}

function toolCategory(name: string): "mcp" | "subagent" | "tool" {
  if (name.startsWith("mcp__")) return "mcp";
  if (name === "Task") return "subagent";
  return "tool";
}

/**
 * Process raw JSONL events into a structured conversation for display.
 */
export function processConversation(
  events: RawEvent[],
  sessionId: string,
  projectPath: string
): ProcessedConversation {
  const plans = extractClaudePlans(events, sessionId, projectPath);
  const messages: ProcessedMessage[] = [];
  const pendingToolCalls = new Map<string, DisplayToolCallBlock>();
  const totalUsage: TokenUsage = {
    input_tokens: 0,
    output_tokens: 0,
    cache_creation_input_tokens: 0,
    cache_read_input_tokens: 0,
  };
  let model: string | undefined;
  let gitBranch: string | undefined;
  let speed: string | undefined;
  let startTime = Infinity;
  let endTime = 0;

  // Context window tracking
  let peakContextWindow = 0;
  let apiCalls = 0;

  // Context analytics accumulators
  const bucketMap = new Map<
    string,
    {
      category: ContextBucket["category"];
      inputTokens: number;
      outputTokens: number;
      cacheWriteTokens: number;
      cacheReadTokens: number;
      calls: number;
    }
  >();
  const steps: ContextStep[] = [];
  let msgIndex = 0;

  function addToBucket(
    label: string,
    category: ContextBucket["category"],
    usage: TokenUsage | undefined
  ) {
    if (!usage) return;
    const existing = bucketMap.get(label) || {
      category,
      inputTokens: 0,
      outputTokens: 0,
      cacheWriteTokens: 0,
      cacheReadTokens: 0,
      calls: 0,
    };
    existing.inputTokens += usage.input_tokens || 0;
    existing.outputTokens += usage.output_tokens || 0;
    existing.cacheWriteTokens += usage.cache_creation_input_tokens || 0;
    existing.cacheReadTokens += usage.cache_read_input_tokens || 0;
    existing.calls += 1;
    bucketMap.set(label, existing);
  }

  for (const event of events) {
    if (event.type === "file-history-snapshot" || event.type === "progress") {
      continue;
    }

    if (event.timestamp) {
      const ts = toEpochMs(event.timestamp);
      if (ts < startTime) startTime = ts;
      if (ts > endTime) endTime = ts;
    }

    if (!gitBranch && event.gitBranch) {
      gitBranch = event.gitBranch;
    }

    if (event.type === "user" && event.message?.role === "user") {
      const content = event.message.content;

      if (Array.isArray(content)) {
        for (const block of content) {
          if (typeof block === "object" && block.type === "tool_result") {
            const toolResult = block as ToolResultBlock;
            const pending = pendingToolCalls.get(toolResult.tool_use_id);
            if (pending) {
              let resultText: string;
              if (typeof toolResult.content === "string") {
                resultText = toolResult.content;
              } else if (Array.isArray(toolResult.content)) {
                resultText = toolResult.content
                  .map((b) => ("text" in b ? b.text : JSON.stringify(b)))
                  .join("\n");
              } else {
                resultText = String(toolResult.content ?? "");
              }
              pending.result = resultText.slice(0, TOOL_RESULT_MAX_LENGTH);
              pending.isError = toolResult.is_error;
            }
            continue;
          }

          if (typeof block === "object" && block.type === "text") {
            messages.push({
              id: event.uuid,
              role: "user",
              timestamp: toEpochMs(event.timestamp),
              blocks: [{ type: "text", text: block.text } as DisplayTextBlock],
            });
          }
        }
      } else if (typeof content === "string" && content.trim()) {
        messages.push({
          id: event.uuid,
          role: "user",
          timestamp: toEpochMs(event.timestamp),
          blocks: [{ type: "text", text: content } as DisplayTextBlock],
        });
      }
    }

    if (event.type === "assistant" && event.message?.role === "assistant") {
      if (!model && event.message.model) {
        model = event.message.model;
      }

      const usage = event.message.usage;
      if (usage) {
        totalUsage.input_tokens += usage.input_tokens || 0;
        totalUsage.output_tokens += usage.output_tokens || 0;
        totalUsage.cache_creation_input_tokens =
          (totalUsage.cache_creation_input_tokens || 0) +
          (usage.cache_creation_input_tokens || 0);
        totalUsage.cache_read_input_tokens =
          (totalUsage.cache_read_input_tokens || 0) +
          (usage.cache_read_input_tokens || 0);
        if (!speed && usage.speed) {
          speed = usage.speed;
        }

        // Track per-call context window size
        apiCalls++;
        const callContext =
          (usage.input_tokens || 0) +
          (usage.cache_creation_input_tokens || 0) +
          (usage.cache_read_input_tokens || 0);
        if (callContext > peakContextWindow) peakContextWindow = callContext;
      }

      const blocks: DisplayBlock[] = [];
      const content = event.message.content;
      const toolNames: string[] = [];
      let hasThinking = false;

      if (Array.isArray(content)) {
        for (const block of content) {
          if (typeof block !== "object") continue;

          switch (block.type) {
            case "text":
              blocks.push({
                type: "text",
                text: block.text,
              } as DisplayTextBlock);
              break;

            case "thinking":
              hasThinking = true;
              blocks.push({
                type: "thinking",
                thinking: block.thinking,
                charCount: block.thinking.length,
              } as DisplayThinkingBlock);
              break;

            case "tool_use": {
              const toolCall: DisplayToolCallBlock = {
                type: "tool_call",
                toolUseId: block.id,
                toolName: block.name,
                input: block.input,
              };
              blocks.push(toolCall);
              pendingToolCalls.set(block.id, toolCall);
              toolNames.push(block.name);
              break;
            }
          }
        }
      }

      if (blocks.length > 0) {
        const idx = msgIndex++;
        messages.push({
          id: event.uuid,
          role: "assistant",
          timestamp: toEpochMs(event.timestamp),
          blocks,
          usage: usage ?? undefined,
          model: event.message.model,
          speed: usage?.speed,
        });

        // --- Context analytics attribution ---
        if (usage && usageTotal(usage) > 0) {
          if (toolNames.length > 0) {
            // Attribute tokens to each tool equally
            const perTool: TokenUsage = {
              input_tokens: Math.round((usage.input_tokens || 0) / toolNames.length),
              output_tokens: Math.round((usage.output_tokens || 0) / toolNames.length),
              cache_creation_input_tokens: Math.round(
                (usage.cache_creation_input_tokens || 0) / toolNames.length
              ),
              cache_read_input_tokens: Math.round(
                (usage.cache_read_input_tokens || 0) / toolNames.length
              ),
            };
            for (const tn of toolNames) {
              addToBucket(tn, toolCategory(tn), perTool);
            }
          } else if (hasThinking) {
            addToBucket("Thinking", "thinking", usage);
          } else {
            addToBucket("Conversation", "conversation", usage);
          }

          // Build per-step entry
          const stepLabel =
            toolNames.length > 0
              ? toolNames.join(", ")
              : hasThinking
                ? "Thinking + text"
                : "Text response";

          const stepCategory: ContextBucket["category"] =
            toolNames.length > 0
              ? toolNames.some((n) => n.startsWith("mcp__"))
                ? "mcp"
                : toolNames.includes("Task")
                  ? "subagent"
                  : "tool"
              : hasThinking
                ? "thinking"
                : "conversation";

          steps.push({
            messageId: event.uuid,
            index: idx,
            role: "assistant",
            label: stepLabel,
            category: stepCategory,
            timestamp: toEpochMs(event.timestamp),
            inputTokens: usage.input_tokens || 0,
            outputTokens: usage.output_tokens || 0,
            cacheWriteTokens: usage.cache_creation_input_tokens || 0,
            cacheReadTokens: usage.cache_read_input_tokens || 0,
            totalTokens: usageTotal(usage),
          });
        }
      }
    }
  }

  // Finalize buckets
  const buckets: ContextBucket[] = Array.from(bucketMap.entries()).map(
    ([label, b]) => ({
      label,
      category: b.category,
      inputTokens: b.inputTokens,
      outputTokens: b.outputTokens,
      cacheWriteTokens: b.cacheWriteTokens,
      cacheReadTokens: b.cacheReadTokens,
      totalTokens:
        b.inputTokens + b.outputTokens + b.cacheWriteTokens + b.cacheReadTokens,
      calls: b.calls,
    })
  );
  buckets.sort((a, b) => b.totalTokens - a.totalTokens);
  steps.sort((a, b) => b.totalTokens - a.totalTokens);

  const contextAnalytics: ContextAnalytics = { buckets, steps };

  const cumulativeTokens =
    totalUsage.input_tokens +
    totalUsage.output_tokens +
    (totalUsage.cache_creation_input_tokens || 0) +
    (totalUsage.cache_read_input_tokens || 0);

  return {
    sessionId,
    projectPath,
    createdAt: startTime === Infinity ? 0 : startTime,
    lastUpdatedAt: endTime,
    isRunning: false,
    messages,
    plans,
    totalUsage,
    model,
    gitBranch,
    startTime: startTime === Infinity ? 0 : startTime,
    endTime,
    subagents: [],
    contextAnalytics,
    contextWindow: {
      peakContextWindow,
      apiCalls,
      cumulativeTokens,
    },
    speed,
  };
}
