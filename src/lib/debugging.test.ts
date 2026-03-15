import test from "node:test";
import assert from "node:assert/strict";
import {
  buildDebugConversationMatches,
  countMatchesByScenario,
  filterDebugConversationMatches,
} from "@/lib/debugging";
import type { ConversationSummary } from "@/lib/types";

function makeConversation(overrides: Partial<ConversationSummary>): ConversationSummary {
  return {
    sessionId: overrides.sessionId ?? "session-1",
    projectPath: overrides.projectPath ?? "-users-tony-code-helaicopter",
    projectName: overrides.projectName ?? "helaicopter",
    threadType: overrides.threadType ?? "main",
    firstMessage: overrides.firstMessage ?? "Fix the broken editor flow and update tests",
    timestamp: overrides.timestamp ?? Date.parse("2026-03-15T10:00:00Z"),
    messageCount: overrides.messageCount ?? 12,
    model: overrides.model,
    totalInputTokens: overrides.totalInputTokens ?? 1000,
    totalOutputTokens: overrides.totalOutputTokens ?? 800,
    totalCacheCreationTokens: overrides.totalCacheCreationTokens ?? 0,
    totalCacheReadTokens: overrides.totalCacheReadTokens ?? 0,
    toolUseCount: overrides.toolUseCount ?? 4,
    failedToolCallCount: overrides.failedToolCallCount ?? 0,
    toolBreakdown: overrides.toolBreakdown ?? {},
    subagentCount: overrides.subagentCount ?? 0,
    subagentTypeBreakdown: overrides.subagentTypeBreakdown ?? {},
    taskCount: overrides.taskCount ?? 0,
    gitBranch: overrides.gitBranch,
    reasoningEffort: overrides.reasoningEffort,
    speed: overrides.speed,
    totalReasoningTokens: overrides.totalReasoningTokens,
  };
}

test("buildDebugConversationMatches classifies editing and test activity", () => {
  const matches = buildDebugConversationMatches([
    makeConversation({
      toolBreakdown: { apply_patch: 2, exec_command: 1 },
      gitBranch: "fix/editor-regression",
    }),
  ]);

  assert.equal(matches.length, 1);
  assert.equal(matches[0]?.conversation.gitBranch, "fix/editor-regression");
  assert(matches[0]?.matches.some((match) => match.id === "editing"));
  assert(matches[0]?.matches.some((match) => match.id === "tests"));
});

test("tool failures and subagent threads get dedicated debug signals", () => {
  const matches = buildDebugConversationMatches([
    makeConversation({
      sessionId: "session-2",
      threadType: "subagent",
      firstMessage: "Debug failing tool call in worker agent",
      failedToolCallCount: 2,
      subagentCount: 3,
      toolBreakdown: { spawn_agent: 1, exec_command: 2 },
    }),
  ]);

  assert.equal(matches.length, 1);
  assert(matches[0]?.matches.some((match) => match.id === "tool-failures"));
  assert(matches[0]?.matches.some((match) => match.id === "multi-agent"));
});

test("filterDebugConversationMatches applies provider, thread type, search, and scenario filters", () => {
  const matches = buildDebugConversationMatches([
    makeConversation({
      sessionId: "claude-edit",
      toolBreakdown: { apply_patch: 1 },
      firstMessage: "Implement the new debugging tab",
    }),
    makeConversation({
      sessionId: "codex-backend",
      projectPath: "codex:-users-tony-code-helaicopter",
      firstMessage: "Update API route and database migration",
      toolBreakdown: { exec_command: 2, apply_patch: 1 },
    }),
  ]);

  const filtered = filterDebugConversationMatches(matches, {
    provider: "codex",
    threadType: "main",
    search: "database migration",
    selectedScenarioIds: ["backend"],
  });

  assert.deepEqual(
    filtered.map((entry) => entry.conversation.sessionId),
    ["codex-backend"]
  );
});

test("countMatchesByScenario totals conversations that matched each scenario", () => {
  const matches = buildDebugConversationMatches([
    makeConversation({
      sessionId: "editing-1",
      toolBreakdown: { apply_patch: 2 },
    }),
    makeConversation({
      sessionId: "editing-2",
      firstMessage: "Playwright test is failing in the frontend editor",
      toolBreakdown: { exec_command: 1 },
      failedToolCallCount: 1,
    }),
  ]);

  const counts = countMatchesByScenario(matches);

  assert.equal(counts.editing, 2);
  assert.equal(counts.tests, 2);
  assert.equal(counts["tool-failures"], 1);
});
