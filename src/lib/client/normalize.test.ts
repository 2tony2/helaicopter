import test from "node:test";
import assert from "node:assert/strict";

import {
  normalizeAnalytics,
  normalizeConversationEvaluations,
  normalizeConversationDetail,
  normalizeDatabaseStatus,
  normalizeEvaluationPrompts,
  normalizeProjects,
  normalizeSubscriptionSettings,
  normalizeTasks,
} from "./normalize";
import {
  conversation,
  conversationDags,
  projects,
  setBaseUrl,
} from "./endpoints";

test("endpoint builders target FastAPI routes without the Next /api prefix", () => {
  setBaseUrl("https://api.example.test/");

  assert.equal(projects(), "https://api.example.test/projects");
  assert.equal(
    conversation("-Users-tony-Code-helaicopter", "session-123"),
    "https://api.example.test/conversations/-Users-tony-Code-helaicopter/session-123"
  );
  assert.equal(
    conversationDags({ project: "repo", days: 7, provider: "all" }),
    "https://api.example.test/conversation-dags?project=repo&days=7"
  );
});

test("endpoint builders infer the local FastAPI origin when the frontend runs on localhost", () => {
  setBaseUrl("");
  const originalWindow = globalThis.window;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      location: {
        protocol: "http:",
        hostname: "localhost",
        port: "3001",
      },
    },
  });

  try {
    assert.equal(projects(), "http://localhost:30000/projects");
    assert.equal(
      conversation("-Users-tony-Code-helaicopter", "session-123"),
      "http://localhost:30000/conversations/-Users-tony-Code-helaicopter/session-123"
    );
    assert.equal(
      conversationDags({ project: "repo", days: 7, provider: "all" }),
      "http://localhost:30000/conversation-dags?project=repo&days=7"
    );
  } finally {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: originalWindow,
    });
  }
});

test("normalizeProjects maps FastAPI project payloads to frontend camelCase types", () => {
  const normalized = normalizeProjects([
    {
      encoded_path: "-Users-tony-Code-helaicopter",
      display_name: "helaicopter",
      full_path: "/Users/tony/Code/helaicopter",
      session_count: 12,
      last_activity: 1763000000000,
    },
  ]);

  assert.deepEqual(normalized, [
    {
      encodedPath: "-Users-tony-Code-helaicopter",
      displayName: "helaicopter",
      fullPath: "/Users/tony/Code/helaicopter",
      sessionCount: 12,
      lastActivity: 1763000000000,
    },
  ]);
});

test("normalizeProjects also accepts existing Next.js camelCase payloads", () => {
  const normalized = normalizeProjects([
    {
      encodedPath: "-Users-tony-Code-helaicopter",
      displayName: "helaicopter",
      fullPath: "/Users/tony/Code/helaicopter",
      sessionCount: 12,
      lastActivity: 1763000000000,
    },
  ]);

  assert.deepEqual(normalized, [
    {
      encodedPath: "-Users-tony-Code-helaicopter",
      displayName: "helaicopter",
      fullPath: "/Users/tony/Code/helaicopter",
      sessionCount: 12,
      lastActivity: 1763000000000,
    },
  ]);
});

test("normalizeConversationDetail preserves token usage semantics expected by the viewer", () => {
  const normalized = normalizeConversationDetail({
    session_id: "session-123",
    project_path: "-Users-tony-Code-helaicopter",
    created_at: 1763000000000,
    last_updated_at: 1763000001000,
    is_running: false,
    messages: [
      {
        id: "msg-1",
        role: "assistant",
        timestamp: 1763000000000,
        blocks: [
          {
            type: "tool_call",
            tool_use_id: "tool-1",
            tool_name: "Bash",
            input: { cmd: "pwd" },
            result: "/tmp",
            is_error: false,
          },
        ],
        usage: {
          input_tokens: 10,
          output_tokens: 20,
          cache_creation_tokens: 3,
          cache_read_tokens: 4,
        },
        reasoning_tokens: 5,
      },
    ],
    plans: [
      {
        id: "plan-1",
        slug: "rollout-plan",
        title: "Rollout plan",
        preview: "Ship it",
        content: "# Rollout",
        provider: "claude",
        timestamp: 1763000000000,
        session_id: "session-123",
        project_path: "-Users-tony-Code-helaicopter",
        source_path: "/tmp/plan.md",
        explanation: "Because",
        steps: [{ step: "Ship it", status: "pending" }],
      },
    ],
    total_usage: {
      input_tokens: 100,
      output_tokens: 200,
      cache_creation_tokens: 30,
      cache_read_tokens: 40,
    },
    start_time: 1763000000000,
    end_time: 1763000001000,
    subagents: [
      {
        agent_id: "agent-1",
        has_file: true,
        project_path: "-Users-tony-Code-helaicopter",
        session_id: "agent-1",
      },
    ],
    context_analytics: {
      buckets: [
        {
          label: "conversation",
          category: "conversation",
          input_tokens: 1,
          output_tokens: 2,
          cache_write_tokens: 3,
          cache_read_tokens: 4,
          total_tokens: 10,
          calls: 1,
        },
      ],
      steps: [
        {
          message_id: "msg-1",
          index: 0,
          role: "assistant",
          label: "conversation",
          category: "conversation",
          timestamp: 1763000000000,
          input_tokens: 1,
          output_tokens: 2,
          cache_write_tokens: 3,
          cache_read_tokens: 4,
          total_tokens: 10,
        },
      ],
    },
    context_window: {
      peak_context_window: 44,
      api_calls: 2,
      cumulative_tokens: 300,
    },
  });

  assert.equal(normalized.sessionId, "session-123");
  assert.deepEqual(normalized.totalUsage, {
    input_tokens: 100,
    output_tokens: 200,
    cache_creation_input_tokens: 30,
    cache_read_input_tokens: 40,
  });
  assert.deepEqual(normalized.messages[0].usage, {
    input_tokens: 10,
    output_tokens: 20,
    cache_creation_input_tokens: 3,
    cache_read_input_tokens: 4,
  });
  assert.equal(normalized.messages[0].blocks[0].toolUseId, "tool-1");
  assert.equal(normalized.plans[0].sessionId, "session-123");
  assert.equal(normalized.subagents[0].agentId, "agent-1");
  assert.equal(normalized.contextAnalytics.buckets[0].cacheWriteTokens, 3);
  assert.equal(normalized.contextWindow.peakContextWindow, 44);
});

test("normalizeAnalytics accepts existing Next.js camelCase payloads", () => {
  const normalized = normalizeAnalytics({
    totalConversations: 4,
    totalInputTokens: 100,
    totalOutputTokens: 25,
    totalCacheCreationTokens: 10,
    totalCacheReadTokens: 5,
    totalReasoningTokens: 3,
    totalToolCalls: 8,
    totalFailedToolCalls: 2,
    modelBreakdown: { "gpt-5": 4 },
    toolBreakdown: { Bash: 8 },
    subagentTypeBreakdown: { planner: 1 },
    modelBreakdownByProvider: {
      "gpt-5": { claude: 0, codex: 4 },
    },
    toolBreakdownByProvider: {
      Bash: { claude: 0, codex: 8 },
    },
    subagentTypeBreakdownByProvider: {
      planner: { claude: 0, codex: 1 },
    },
    dailyUsage: [
      {
        date: "2026-03-18",
        inputTokens: 100,
        outputTokens: 25,
        cacheWriteTokens: 10,
        cacheReadTokens: 5,
        conversations: 4,
        subagents: 1,
        claudeInputTokens: 0,
        claudeOutputTokens: 0,
        claudeCacheWriteTokens: 0,
        claudeCacheReadTokens: 0,
        codexInputTokens: 100,
        codexOutputTokens: 25,
        codexCacheWriteTokens: 10,
        codexCacheReadTokens: 5,
        claudeConversations: 0,
        codexConversations: 4,
        claudeSubagents: 0,
        codexSubagents: 1,
      },
    ],
    rates: {
      spend: { perHour: 1, perDay: 2, perWeek: 14, perMonth: 60 },
      tokens: { perHour: 10, perDay: 20, perWeek: 140, perMonth: 600 },
      conversations: { perHour: 0.5, perDay: 1, perWeek: 7, perMonth: 30 },
      toolCalls: { perHour: 1, perDay: 2, perWeek: 14, perMonth: 60 },
    },
    timeSeries: {
      hourly: [],
      daily: [
        {
          key: "2026-03-18T00:00:00.000Z",
          label: "2026-03-18",
          start: "2026-03-18T00:00:00.000Z",
          end: "2026-03-19T00:00:00.000Z",
          estimatedCost: 12.5,
          claudeEstimatedCost: 0,
          codexEstimatedCost: 12.5,
          inputTokens: 100,
          outputTokens: 25,
          cacheWriteTokens: 10,
          cacheReadTokens: 5,
          reasoningTokens: 3,
          totalTokens: 140,
          conversations: 4,
          toolCalls: 8,
          failedToolCalls: 2,
          toolErrorRatePct: 25,
          subagents: 1,
          claudeInputTokens: 0,
          claudeOutputTokens: 0,
          claudeCacheWriteTokens: 0,
          claudeCacheReadTokens: 0,
          claudeReasoningTokens: 0,
          claudeTotalTokens: 0,
          claudeConversations: 0,
          claudeToolCalls: 0,
          claudeFailedToolCalls: 0,
          claudeToolErrorRatePct: 0,
          claudeSubagents: 0,
          codexInputTokens: 100,
          codexOutputTokens: 25,
          codexCacheWriteTokens: 10,
          codexCacheReadTokens: 5,
          codexReasoningTokens: 3,
          codexTotalTokens: 140,
          codexConversations: 4,
          codexToolCalls: 8,
          codexFailedToolCalls: 2,
          codexToolErrorRatePct: 25,
          codexSubagents: 1,
        },
      ],
      weekly: [],
      monthly: [],
    },
    estimatedCost: 12.5,
    costBreakdown: {
      totalCost: 12.5,
      inputCost: 6,
      outputCost: 2,
      cacheWriteCost: 3,
      cacheReadCost: 1.5,
      reasoningCost: 0,
    },
    costBreakdownByProvider: {
      codex: {
        totalCost: 12.5,
        inputCost: 6,
        outputCost: 2,
        cacheWriteCost: 3,
        cacheReadCost: 1.5,
        reasoningCost: 0,
      },
    },
    costBreakdownByModel: {
      "gpt-5": {
        totalCost: 12.5,
        inputCost: 6,
        outputCost: 2,
        cacheWriteCost: 3,
        cacheReadCost: 1.5,
        reasoningCost: 0,
      },
    },
  });

  assert.equal(normalized.totalConversations, 4);
  assert.equal(normalized.dailyUsage.length, 1);
  assert.equal(normalized.timeSeries.daily.length, 1);
  assert.equal(normalized.costBreakdown.totalCost, 12.5);
  assert.equal(normalized.rates.spend.perDay, 2);
});

test("normalizeTasks unwraps the FastAPI task envelope for the existing viewer", () => {
  assert.deepEqual(
    normalizeTasks({
      session_id: "session-123",
      tasks: [{ taskId: "T017", title: "Frontend cutover" }],
    }),
    [{ taskId: "T017", title: "Frontend cutover" }]
  );
});

test("normalizeDatabaseStatus tolerates snake_case payloads for refresh responses", () => {
  const normalized = normalizeDatabaseStatus({
    status: "failed",
    trigger: "manual",
    started_at: "2026-03-18T10:00:00Z",
    finished_at: "2026-03-18T10:00:05Z",
    duration_ms: 5000,
    error: "refresh exploded",
    last_successful_refresh_at: "2026-03-18T09:00:00Z",
    idempotency_key: "refresh-123",
    scope_label: "Historical conversations",
    window_days: 30,
    window_start: "2026-02-17T00:00:00Z",
    window_end: "2026-03-18T00:00:00Z",
    source_conversation_count: 42,
    refresh_interval_minutes: 360,
    runtime: {
      analytics_read_backend: "legacy",
      conversation_summary_read_backend: "legacy",
    },
    databases: {
      sqlite: {
        key: "sqlite",
        label: "SQLite Metadata Store",
        engine: "SQLite",
        role: "metadata",
        availability: "ready",
        table_count: 4,
        tables: [
          {
            name: "evaluation_prompts",
            row_count: 3,
            columns: [
              {
                name: "prompt_id",
                type: "TEXT",
                nullable: false,
                default_value: null,
                is_primary_key: true,
                references: null,
              },
            ],
          },
        ],
      },
      legacy_duckdb: {
        key: "legacy_duckdb",
        label: "Legacy DuckDB Snapshot",
        engine: "DuckDB",
        role: "legacy_debug",
        availability: "missing",
        table_count: 0,
        tables: [],
      },
    },
  });

  assert.equal(normalized.startedAt, "2026-03-18T10:00:00Z");
  assert.equal(normalized.durationMs, 5000);
  assert.equal(normalized.runtime.analyticsReadBackend, "legacy");
  assert.equal(normalized.databases.sqlite.tableCount, 4);
  assert.equal(normalized.databases.sqlite.tables[0].rowCount, 3);
  assert.equal(normalized.databases.sqlite.tables[0].columns[0].defaultValue, null);
  assert.equal(normalized.databases.sqlite.tables[0].columns[0].isPrimaryKey, true);
  assert.equal(normalized.databases.legacyDuckdb.key, "legacy_duckdb");
});

test("normalizeEvaluationPrompts and normalizeConversationEvaluations map prompt and job records", () => {
  const prompts = normalizeEvaluationPrompts([
    {
      prompt_id: "prompt-1",
      name: "Failure Sweep",
      description: "Inspect failures",
      prompt_text: "Look for recoverable errors.",
      is_default: false,
      created_at: "2026-03-18T10:00:00Z",
      updated_at: "2026-03-18T10:01:00Z",
    },
  ]);
  const evaluations = normalizeConversationEvaluations([
    {
      evaluation_id: "evaluation-1",
      conversation_id: "claude:session-1",
      prompt_id: "prompt-1",
      provider: "codex",
      model: "gpt-5",
      status: "running",
      scope: "failed_tool_calls",
      selection_instruction: "Focus on the failure cluster.",
      prompt_name: "Failure Sweep",
      prompt_text: "Look for recoverable errors.",
      report_markdown: null,
      raw_output: null,
      error_message: null,
      command: "codex exec --model gpt-5",
      created_at: "2026-03-18T10:00:00Z",
      finished_at: null,
      duration_ms: null,
    },
  ]);

  assert.deepEqual(prompts, [
    {
      promptId: "prompt-1",
      name: "Failure Sweep",
      description: "Inspect failures",
      promptText: "Look for recoverable errors.",
      isDefault: false,
      createdAt: "2026-03-18T10:00:00Z",
      updatedAt: "2026-03-18T10:01:00Z",
    },
  ]);
  assert.deepEqual(evaluations, [
    {
      evaluationId: "evaluation-1",
      conversationId: "claude:session-1",
      promptId: "prompt-1",
      provider: "codex",
      model: "gpt-5",
      status: "running",
      scope: "failed_tool_calls",
      selectionInstruction: "Focus on the failure cluster.",
      promptName: "Failure Sweep",
      promptText: "Look for recoverable errors.",
      reportMarkdown: null,
      rawOutput: null,
      errorMessage: null,
      command: "codex exec --model gpt-5",
      createdAt: "2026-03-18T10:00:00Z",
      finishedAt: null,
      durationMs: null,
    },
  ]);
});

test("normalizeSubscriptionSettings maps provider records for analytics settings", () => {
  const normalized = normalizeSubscriptionSettings({
    claude: {
      provider: "claude",
      has_subscription: false,
      monthly_cost: 123.45,
      updated_at: "2026-03-18T10:00:00Z",
    },
    codex: {
      provider: "codex",
      has_subscription: true,
      monthly_cost: 200,
      updated_at: "2026-03-18T10:00:00Z",
    },
  });

  assert.deepEqual(normalized, {
    claude: {
      provider: "claude",
      hasSubscription: false,
      monthlyCost: 123.45,
      updatedAt: "2026-03-18T10:00:00Z",
    },
    codex: {
      provider: "codex",
      hasSubscription: true,
      monthlyCost: 200,
      updatedAt: "2026-03-18T10:00:00Z",
    },
  });
});
