import { PRICING, OPENAI_PRICING, DEFAULT_PRICING, type ModelPricing } from "./constants";
import type { TokenUsage } from "./types";

/**
 * Resolve pricing for a model ID. Tries exact match, then prefix match, then default.
 */
export function getPricing(model?: string): ModelPricing {
  if (!model) return DEFAULT_PRICING;
  if (PRICING[model]) return PRICING[model];
  if (OPENAI_PRICING[model]) return OPENAI_PRICING[model];
  // Prefix match: "claude-opus-4-6[1m]" → "claude-opus-4-6"
  for (const key of Object.keys(PRICING)) {
    if (model.startsWith(key)) return PRICING[key];
  }
  // OpenAI prefix match
  for (const key of Object.keys(OPENAI_PRICING)) {
    if (model.startsWith(key)) return OPENAI_PRICING[key];
  }
  // OpenAI model family match (order matters: check more specific patterns first)
  if (model.includes("gpt-5.4") || model.includes("gpt5.4"))
    return OPENAI_PRICING["gpt-5.4"];
  if (model.includes("gpt-5.2") || model.includes("gpt5.2"))
    return OPENAI_PRICING["gpt-5.2"];
  if (model.includes("gpt-5.1") || model.includes("gpt5.1"))
    return OPENAI_PRICING["gpt-5.1"];
  if (model.includes("gpt-5-mini") || model.includes("gpt5-mini"))
    return OPENAI_PRICING["gpt-5-mini"];
  if (model.includes("gpt-5") || model.includes("gpt5"))
    return OPENAI_PRICING["gpt-5"];
  if (model.includes("o4-mini"))
    return OPENAI_PRICING["o4-mini"];
  if (model.includes("o3"))
    return OPENAI_PRICING["o3"];
  // Claude family match
  if (model.includes("opus-4-6") || model.includes("opus-4-5"))
    return PRICING["claude-opus-4-6"];
  if (model.includes("opus-4-1") || model.includes("opus-4"))
    return PRICING["claude-opus-4"];
  if (model.includes("sonnet"))
    return PRICING["claude-sonnet-4-5-20250929"];
  if (model.includes("haiku"))
    return PRICING["claude-haiku-4-5-20251001"];
  return DEFAULT_PRICING;
}

export interface CostBreakdown {
  inputCost: number;
  outputCost: number;
  cacheWriteCost: number;
  cacheReadCost: number;
  totalCost: number;
}

/**
 * Calculate dollar cost from token usage and model.
 * Claude uses explicit cache-write pricing; OpenAI/Codex bills cache fills as normal input.
 */
export function calculateCost(
  usage: TokenUsage | { inputTokens: number; outputTokens: number; cacheWriteTokens: number; cacheReadTokens: number },
  model?: string
): CostBreakdown {
  const p = getPricing(model);

  let input: number, output: number, cacheWrite: number, cacheRead: number;

  if ("input_tokens" in usage) {
    input = usage.input_tokens || 0;
    output = usage.output_tokens || 0;
    cacheWrite = usage.cache_creation_input_tokens || 0;
    cacheRead = usage.cache_read_input_tokens || 0;
  } else {
    input = usage.inputTokens || 0;
    output = usage.outputTokens || 0;
    cacheWrite = usage.cacheWriteTokens || 0;
    cacheRead = usage.cacheReadTokens || 0;
  }

  const inputCost = (input / 1_000_000) * p.input;
  const outputCost = (output / 1_000_000) * p.output;
  const cacheWriteCost = (cacheWrite / 1_000_000) * p.cacheWrite5m;
  const cacheReadCost = (cacheRead / 1_000_000) * p.cacheRead;

  return {
    inputCost,
    outputCost,
    cacheWriteCost,
    cacheReadCost,
    totalCost: inputCost + outputCost + cacheWriteCost + cacheReadCost,
  };
}

/**
 * Calculate cost with long-context premium (>200K active input tokens).
 * The 200K threshold is based on active (non-cached) input tokens only.
 * Opus 4.6: input 2x, output 1.5x. Sonnet: input 2x, output 1.5x.
 */
export function calculateCostWithLongContext(
  usage: TokenUsage,
  model?: string
): CostBreakdown {
  const base = calculateCost(usage, model);
  const activeInput = usage.input_tokens || 0;

  if (activeInput <= 200_000) return base;

  // Long context premium applies to the entire request
  const isOpus = model?.includes("opus-4-6") || model?.includes("opus-4-5");
  const isSonnet =
    model?.includes("sonnet-4-6") ||
    model?.includes("sonnet-4-5") ||
    model?.includes("sonnet-4");

  if (isOpus || isSonnet) {
    // Input doubles, output 1.5x
    return {
      inputCost: base.inputCost * 2,
      outputCost: base.outputCost * 1.5,
      cacheWriteCost: base.cacheWriteCost * 2,
      cacheReadCost: base.cacheReadCost * 2,
      totalCost:
        base.inputCost * 2 +
        base.outputCost * 1.5 +
        base.cacheWriteCost * 2 +
        base.cacheReadCost * 2,
    };
  }

  return base;
}

/**
 * Format a dollar amount for display.
 */
export function formatCost(amount: number): string {
  if (amount >= 1) return `$${amount.toFixed(2)}`;
  if (amount >= 0.01) return `$${amount.toFixed(2)}`;
  if (amount >= 0.001) return `$${amount.toFixed(3)}`;
  if (amount === 0) return "$0.00";
  return `$${amount.toFixed(4)}`;
}
