import test from "node:test";
import assert from "node:assert/strict";
import { normalizeAnalytics } from "./normalize";

test("normalizeAnalytics tolerates empty/partial payloads and fills defaults", () => {
  const normalized = normalizeAnalytics({
    total_conversations: undefined,
    // Missing most fields; ensure numbers become 0 and arrays/maps materialize
  } as unknown as Record<string, unknown>);

  assert.equal(normalized.totalConversations, 0);
  assert.equal(normalized.totalInputTokens, 0);
  assert.deepEqual(normalized.modelBreakdown, {});
  assert.deepEqual(normalized.dailyUsage, []);
  assert.deepEqual(normalized.timeSeries.hourly, []);
  assert.equal(normalized.costBreakdown.totalCost, 0);
});
