import test from "node:test";
import assert from "node:assert/strict";

import { totalTokensForConversationSummary } from "./conversation-tokens";

test("totalTokensForConversationSummary uses Codex-native totals", () => {
  assert.equal(
    totalTokensForConversationSummary({
      provider: "codex",
      projectPath: "codex:-Users-tony-Code-helaicopter",
      totalInputTokens: 240,
      totalOutputTokens: 80,
      totalCacheCreationTokens: 0,
      totalCacheReadTokens: 16,
    }),
    320
  );
});

test("totalTokensForConversationSummary keeps cache dimensions for Claude", () => {
  assert.equal(
    totalTokensForConversationSummary({
      provider: "claude",
      projectPath: "-Users-tony-Code-helaicopter",
      totalInputTokens: 120,
      totalOutputTokens: 45,
      totalCacheCreationTokens: 12,
      totalCacheReadTokens: 6,
    }),
    183
  );
});
