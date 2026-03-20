import test from "node:test";
import assert from "node:assert/strict";
import { getPricing, calculateCost, calculateCostWithLongContext, formatCost } from "./pricing";
import { PRICING, OPENAI_PRICING, DEFAULT_PRICING } from "./constants";

test("getPricing falls back for unknown or missing models", () => {
  assert.equal(getPricing(undefined), DEFAULT_PRICING);
  assert.equal(getPricing(""), DEFAULT_PRICING);
  assert.equal(getPricing("totally-unknown"), DEFAULT_PRICING);
});

test("getPricing resolves family matches", () => {
  assert.equal(getPricing("model-gpt-5.4-x"), OPENAI_PRICING["gpt-5.4"]);
  assert.equal(getPricing("o4-mini-new"), OPENAI_PRICING["o4-mini"]);
  assert.equal(getPricing("some-opus-4-6"), PRICING["claude-opus-4-6"]);
  assert.equal(getPricing("some-opus-4-1"), PRICING["claude-opus-4"]);
  assert.equal(getPricing("some-sonnet"), PRICING["claude-sonnet-4-5-20250929"]);
});

test("calculateCost handles zero and small usage", () => {
  const zero = calculateCost({ inputTokens: 0, outputTokens: 0, cacheWriteTokens: 0, cacheReadTokens: 0 });
  assert.equal(zero.totalCost, 0);

  const tiny = calculateCost({ inputTokens: 1, outputTokens: 1, cacheWriteTokens: 1, cacheReadTokens: 1 },
    "claude-sonnet-4-5-20250929");
  assert.ok(tiny.totalCost > 0);
  assert.equal(tiny.totalCost, tiny.inputCost + tiny.outputCost + tiny.cacheWriteCost + tiny.cacheReadCost);
});

test("calculateCostWithLongContext applies premium for >200k on supported models", () => {
  const usage = { input_tokens: 201_000, output_tokens: 10_000 } as const;
  const base = calculateCost({ inputTokens: 201_000, outputTokens: 10_000, cacheWriteTokens: 0, cacheReadTokens: 0 },
    "claude-sonnet-4-5-20250929");
  const withPremium = calculateCostWithLongContext(usage, "claude-sonnet-4-5-20250929");
  assert.ok(withPremium.totalCost > base.totalCost);

  const openaiPremium = calculateCostWithLongContext(usage, "gpt-5");
  // No premium for non‑Claude families in frontend logic
  const openaiBase = calculateCost({ inputTokens: 201_000, outputTokens: 10_000, cacheWriteTokens: 0, cacheReadTokens: 0 }, "gpt-5");
  assert.equal(openaiPremium.totalCost, openaiBase.totalCost);
});

test("formatCost handles small and large amounts", () => {
  assert.equal(formatCost(0), "$0.00");
  assert.equal(formatCost(0.0099), "$0.010");
  assert.equal(formatCost(0.1), "$0.10");
  assert.equal(formatCost(1.234), "$1.23");
});
