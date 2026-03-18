export interface ModelPricing {
  input: number;
  output: number;
  cacheWrite5m: number;
  cacheWrite1h: number;
  cacheRead: number;
}

// Token pricing per 1M tokens (USD) - from platform.claude.com/docs/en/about-claude/pricing
export const PRICING: Record<string, ModelPricing> = {
  // Opus family
  "claude-opus-4-6": {
    input: 5.0,
    output: 25.0,
    cacheWrite5m: 6.25,
    cacheWrite1h: 10.0,
    cacheRead: 0.5,
  },
  "claude-opus-4-5-20251101": {
    input: 5.0,
    output: 25.0,
    cacheWrite5m: 6.25,
    cacheWrite1h: 10.0,
    cacheRead: 0.5,
  },
  "claude-opus-4-1": {
    input: 15.0,
    output: 75.0,
    cacheWrite5m: 18.75,
    cacheWrite1h: 30.0,
    cacheRead: 1.5,
  },
  "claude-opus-4": {
    input: 15.0,
    output: 75.0,
    cacheWrite5m: 18.75,
    cacheWrite1h: 30.0,
    cacheRead: 1.5,
  },
  // Sonnet family
  "claude-sonnet-4-6": {
    input: 3.0,
    output: 15.0,
    cacheWrite5m: 3.75,
    cacheWrite1h: 6.0,
    cacheRead: 0.3,
  },
  "claude-sonnet-4-5-20250929": {
    input: 3.0,
    output: 15.0,
    cacheWrite5m: 3.75,
    cacheWrite1h: 6.0,
    cacheRead: 0.3,
  },
  "claude-sonnet-4": {
    input: 3.0,
    output: 15.0,
    cacheWrite5m: 3.75,
    cacheWrite1h: 6.0,
    cacheRead: 0.3,
  },
  // Haiku family
  "claude-haiku-4-5-20251001": {
    input: 1.0,
    output: 5.0,
    cacheWrite5m: 1.25,
    cacheWrite1h: 2.0,
    cacheRead: 0.1,
  },
  "claude-haiku-3-5": {
    input: 0.8,
    output: 4.0,
    cacheWrite5m: 1.0,
    cacheWrite1h: 1.6,
    cacheRead: 0.08,
  },
  "claude-haiku-3": {
    input: 0.25,
    output: 1.25,
    cacheWrite5m: 0.3,
    cacheWrite1h: 0.5,
    cacheRead: 0.03,
  },
};

// OpenAI / Codex models
// OpenAI bills cache fills as normal input, so there is no separate cache-write line item here.
// cacheRead maps to discounted "Cached Input" pricing.
export const OPENAI_PRICING: Record<string, ModelPricing> = {
  "gpt-5.4": {
    input: 2.5,
    output: 15.0,
    cacheWrite5m: 0,
    cacheWrite1h: 0,
    cacheRead: 0.25,
  },
  "gpt-5.2": {
    input: 1.75,
    output: 14.0,
    cacheWrite5m: 0,
    cacheWrite1h: 0,
    cacheRead: 0.175,
  },
  "gpt-5.1": {
    input: 1.25,
    output: 10.0,
    cacheWrite5m: 0,
    cacheWrite1h: 0,
    cacheRead: 0.125,
  },
  "gpt-5": {
    input: 1.25,
    output: 10.0,
    cacheWrite5m: 0,
    cacheWrite1h: 0,
    cacheRead: 0.125,
  },
  "gpt-5-mini": {
    input: 0.25,
    output: 2.0,
    cacheWrite5m: 0,
    cacheWrite1h: 0,
    cacheRead: 0.025,
  },
  "o3": {
    input: 2.0,
    output: 8.0,
    cacheWrite5m: 0,
    cacheWrite1h: 0,
    cacheRead: 0.5,
  },
  "o4-mini": {
    input: 1.1,
    output: 4.4,
    cacheWrite5m: 0,
    cacheWrite1h: 0,
    cacheRead: 0.275,
  },
};

// Fallback for unknown models - use Opus 4.6 pricing (most common in data)
export const DEFAULT_PRICING: ModelPricing = PRICING["claude-opus-4-6"];

export const TOOL_RESULT_MAX_LENGTH = 10_000;
