import type {
  ProcessedConversation,
  ProcessedMessage,
  DisplayBlock,
  DisplayTextBlock,
  DisplayThinkingBlock,
  DisplayToolCallBlock,
  TokenUsage,
  ContextBucket,
  ContextStep,
  ContextAnalytics,
} from "./types";
import type { CodexRawLine } from "./codex-types";
import { codexToolDisplayName } from "./codex-jsonl-parser";
import { TOOL_RESULT_MAX_LENGTH } from "./constants";

function usageTotal(u: TokenUsage | undefined) {
  if (!u) return 0;
  return (
    (u.input_tokens || 0) +
    (u.output_tokens || 0) +
    (u.cache_creation_input_tokens || 0) +
    (u.cache_read_input_tokens || 0)
  );
}

/**
 * Process Codex session JSONL lines into the same ProcessedConversation
 * structure used for Claude conversations.
 *
 * Key differences from Claude format:
 * - Messages, function calls, and tool results are separate line items (not nested blocks)
 * - Token usage comes from event_msg[token_count] events (cumulative + per-step)
 * - Reasoning is in separate response_item[reasoning] or event_msg[agent_reasoning]
 * - Tool calls: exec_command (shell) and apply_patch (file edits) are the main tools
 */
export function processCodexConversation(
  lines: CodexRawLine[],
  sessionId: string,
  projectPath: string
): ProcessedConversation {
  const messages: ProcessedMessage[] = [];
  const pendingToolCalls = new Map<string, DisplayToolCallBlock>();
  let totalUsage: TokenUsage = {
    input_tokens: 0,
    output_tokens: 0,
    cache_creation_input_tokens: 0,
    cache_read_input_tokens: 0,
  };
  let model: string | undefined;
  let gitBranch: string | undefined;
  let reasoningEffort: string | undefined;
  let totalReasoningTokens = 0;
  let startTime = Infinity;
  let endTime = 0;

  // Context window tracking
  let peakContextWindow = 0;
  let apiCalls = 0;

  // Context analytics
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

  // Track token deltas between token_count events
  let prevTotalTokens = {
    input_tokens: 0,
    cached_input_tokens: 0,
    output_tokens: 0,
    reasoning_output_tokens: 0,
  };

  // Buffer to accumulate blocks between token_count events
  let pendingBlocks: DisplayBlock[] = [];
  let pendingToolNames: string[] = [];
  let hasThinking = false;
  let lastAssistantTimestamp = 0;
  let lastAssistantId = "";
  let pendingReasoningTokens = 0;

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

  function flushPendingMessage(stepUsage: TokenUsage | undefined) {
    if (pendingBlocks.length === 0) return;

    const msg: ProcessedMessage = {
      id: lastAssistantId || `codex-${msgIndex}`,
      role: "assistant",
      timestamp: lastAssistantTimestamp,
      blocks: [...pendingBlocks],
      usage: stepUsage,
      model,
      reasoningTokens: pendingReasoningTokens > 0 ? pendingReasoningTokens : undefined,
    };
    messages.push(msg);
    pendingReasoningTokens = 0;

    // Context analytics
    if (stepUsage && usageTotal(stepUsage) > 0) {
      if (pendingToolNames.length > 0) {
        const perTool: TokenUsage = {
          input_tokens: Math.round(
            (stepUsage.input_tokens || 0) / pendingToolNames.length
          ),
          output_tokens: Math.round(
            (stepUsage.output_tokens || 0) / pendingToolNames.length
          ),
          cache_creation_input_tokens: Math.round(
            (stepUsage.cache_creation_input_tokens || 0) /
              pendingToolNames.length
          ),
          cache_read_input_tokens: Math.round(
            (stepUsage.cache_read_input_tokens || 0) / pendingToolNames.length
          ),
        };
        for (const tn of pendingToolNames) {
          addToBucket(tn, "tool", perTool);
        }
      } else if (hasThinking) {
        addToBucket("Thinking", "thinking", stepUsage);
      } else {
        addToBucket("Conversation", "conversation", stepUsage);
      }

      const stepLabel =
        pendingToolNames.length > 0
          ? pendingToolNames.join(", ")
          : hasThinking
            ? "Thinking + text"
            : "Text response";

      steps.push({
        messageId: msg.id,
        index: msgIndex,
        role: "assistant",
        label: stepLabel,
        category:
          pendingToolNames.length > 0
            ? "tool"
            : hasThinking
              ? "thinking"
              : "conversation",
        timestamp: lastAssistantTimestamp,
        inputTokens: stepUsage.input_tokens || 0,
        outputTokens: stepUsage.output_tokens || 0,
        cacheWriteTokens: stepUsage.cache_creation_input_tokens || 0,
        cacheReadTokens: stepUsage.cache_read_input_tokens || 0,
        totalTokens: usageTotal(stepUsage),
      });
    }

    msgIndex++;
    pendingBlocks = [];
    pendingToolNames = [];
    hasThinking = false;
  }

  for (const line of lines) {
    const ts = new Date(line.timestamp).getTime();
    if (ts < startTime) startTime = ts;
    if (ts > endTime) endTime = ts;

    // --- session_meta ---
    if (line.type === "session_meta") {
      const p = line.payload as Record<string, unknown>;
      const cwdVal = p.cwd as string | undefined;
      if (cwdVal) {
        // Extract git branch from cwd if it contains branch info
        // (Codex stores git info in SQLite, not in JSONL)
      }
      continue;
    }

    // --- turn_context ---
    if (line.type === "turn_context") {
      const p = line.payload as Record<string, unknown>;
      if (typeof p.model === "string" && p.model.trim()) {
        model = p.model;
      }
      if (typeof p.reasoning_effort === "string" && p.reasoning_effort.trim()) {
        reasoningEffort = p.reasoning_effort;
      }
      continue;
    }

    // --- event_msg ---
    if (line.type === "event_msg") {
      const p = line.payload as Record<string, unknown>;

      if (p.type === "token_count") {
        const info = p.info as {
          total_token_usage?: {
            input_tokens: number;
            cached_input_tokens: number;
            output_tokens: number;
            reasoning_output_tokens: number;
            total_tokens: number;
          };
          last_token_usage?: {
            input_tokens: number;
            cached_input_tokens: number;
            output_tokens: number;
            reasoning_output_tokens: number;
            total_tokens: number;
          };
          model_context_window?: number;
        } | null;

        if (info?.total_token_usage) {
          const total = info.total_token_usage;

          // Compute delta from previous
          const deltaInput =
            total.input_tokens - prevTotalTokens.input_tokens;
          const deltaCached =
            total.cached_input_tokens - prevTotalTokens.cached_input_tokens;
          const deltaOutput =
            total.output_tokens - prevTotalTokens.output_tokens;
          const deltaReasoning =
            total.reasoning_output_tokens - prevTotalTokens.reasoning_output_tokens;

          const stepUsage: TokenUsage = {
            input_tokens: deltaInput,
            output_tokens: deltaOutput,
            cache_creation_input_tokens: 0, // Codex doesn't have cache write
            cache_read_input_tokens: deltaCached,
          };

          // Track reasoning tokens
          if (deltaReasoning > 0) {
            totalReasoningTokens += deltaReasoning;
            pendingReasoningTokens = deltaReasoning;
          }

          // Track context window
          apiCalls++;
          const callContext = deltaInput + deltaCached;
          if (callContext > peakContextWindow) peakContextWindow = callContext;

          // Flush accumulated blocks as one message
          flushPendingMessage(stepUsage);

          prevTotalTokens = {
            input_tokens: total.input_tokens,
            cached_input_tokens: total.cached_input_tokens,
            output_tokens: total.output_tokens,
            reasoning_output_tokens: total.reasoning_output_tokens,
          };
        }
      }

      // Skip agent_reasoning — duplicates reasoning response_items
      // Skip agent_message — duplicates assistant message response_items

      continue;
    }

    // --- response_item ---
    if (line.type === "response_item") {
      const p = line.payload as Record<string, unknown>;

      // User message
      if (p.type === "message" && p.role === "user") {
        const content = p.content as Array<{ type: string; text: string }>;
        if (Array.isArray(content)) {
          for (const block of content) {
            // Skip system/developer injected content
            if (
              block.type === "input_text" &&
              !block.text.startsWith("<") &&
              block.text.trim()
            ) {
              messages.push({
                id: `user-${msgIndex++}`,
                role: "user",
                timestamp: ts,
                blocks: [
                  { type: "text", text: block.text } as DisplayTextBlock,
                ],
              });
            }
          }
        }
        continue;
      }

      // Developer message — skip (system prompts, permissions)
      if (p.type === "message" && p.role === "developer") continue;

      // Assistant message
      if (p.type === "message" && p.role === "assistant") {
        const content = p.content as Array<{ type: string; text: string }>;
        if (Array.isArray(content)) {
          for (const block of content) {
            if (block.type === "output_text" && block.text.trim()) {
              pendingBlocks.push({
                type: "text",
                text: block.text,
              } as DisplayTextBlock);
            }
          }
        }
        lastAssistantTimestamp = ts;
        lastAssistantId = `assistant-${msgIndex}`;
        continue;
      }

      // Reasoning
      if (p.type === "reasoning") {
        const summary = p.summary as Array<{ type: string; text: string }>;
        if (Array.isArray(summary)) {
          for (const s of summary) {
            if (s.text) {
              hasThinking = true;
              pendingBlocks.push({
                type: "thinking",
                thinking: s.text,
                charCount: s.text.length,
              } as DisplayThinkingBlock);
            }
          }
        }
        continue;
      }

      // Function call (exec_command)
      if (p.type === "function_call") {
        const name = codexToolDisplayName((p.name as string) || "unknown");
        let input: Record<string, unknown> = {};
        try {
          input = JSON.parse(p.arguments as string);
        } catch {
          input = { raw: p.arguments };
        }
        const callId = p.call_id as string;
        const toolCall: DisplayToolCallBlock = {
          type: "tool_call",
          toolUseId: callId,
          toolName: name,
          input,
        };
        pendingBlocks.push(toolCall);
        pendingToolCalls.set(callId, toolCall);
        pendingToolNames.push(name);
        lastAssistantTimestamp = ts;
        lastAssistantId = `assistant-${msgIndex}`;
        continue;
      }

      // Function call output
      if (p.type === "function_call_output") {
        const callId = p.call_id as string;
        const output = p.output as string;
        const pending = pendingToolCalls.get(callId);
        if (pending) {
          pending.result = (output || "").slice(0, TOOL_RESULT_MAX_LENGTH);
          // Check for error in output
          if (output && output.includes("Process exited with code")) {
            const exitMatch = output.match(/Process exited with code (\d+)/);
            if (exitMatch && exitMatch[1] !== "0") {
              pending.isError = true;
            }
          }
        }
        continue;
      }

      // Custom tool call (apply_patch)
      if (p.type === "custom_tool_call") {
        const name = codexToolDisplayName((p.name as string) || "unknown");
        const callId = p.call_id as string;
        const input = { patch: p.input as string };
        const toolCall: DisplayToolCallBlock = {
          type: "tool_call",
          toolUseId: callId,
          toolName: name,
          input,
        };
        pendingBlocks.push(toolCall);
        pendingToolCalls.set(callId, toolCall);
        pendingToolNames.push(name);
        lastAssistantTimestamp = ts;
        lastAssistantId = `assistant-${msgIndex}`;
        continue;
      }

      // Custom tool call output
      if (p.type === "custom_tool_call_output") {
        const callId = p.call_id as string;
        const rawOutput = p.output as string;
        const pending = pendingToolCalls.get(callId);
        if (pending) {
          let outputText = rawOutput;
          try {
            const parsed = JSON.parse(rawOutput);
            outputText = parsed.output || rawOutput;
          } catch {
            // use raw
          }
          pending.result = outputText.slice(0, TOOL_RESULT_MAX_LENGTH);
          if (rawOutput.includes('"exit_code":') && !rawOutput.includes('"exit_code":0')) {
            pending.isError = true;
          }
        }
        continue;
      }

      // Web search call
      if (p.type === "web_search_call") {
        const action =
          (p.action as
            | { type?: string; query?: string; queries?: string[] }
            | undefined) || {};
        const queries = Array.isArray(action.queries)
          ? action.queries.filter(
              (query): query is string =>
                typeof query === "string" && query.trim().length > 0
            )
          : [];
        const input: Record<string, unknown> = {};
        if (action.type) input.type = action.type;
        if (action.query) input.query = action.query;
        if (queries.length > 0) input.queries = queries;

        const toolCall: DisplayToolCallBlock = {
          type: "tool_call",
          toolUseId: `web-search-${msgIndex}-${ts}`,
          toolName: codexToolDisplayName("web_search_call"),
          input,
          result: typeof p.status === "string" ? `Status: ${p.status}` : undefined,
        };
        pendingBlocks.push(toolCall);
        pendingToolNames.push(toolCall.toolName);
        lastAssistantTimestamp = ts;
        lastAssistantId = `assistant-${msgIndex}`;
        continue;
      }
    }
  }

  // Flush any remaining blocks
  flushPendingMessage(undefined);

  // Compute final totals from last cumulative token_count
  totalUsage = {
    input_tokens: prevTotalTokens.input_tokens,
    output_tokens: prevTotalTokens.output_tokens,
    cache_creation_input_tokens: 0,
    cache_read_input_tokens: prevTotalTokens.cached_input_tokens,
  };

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
    messages,
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
    reasoningEffort,
    totalReasoningTokens: totalReasoningTokens > 0 ? totalReasoningTokens : undefined,
  };
}
