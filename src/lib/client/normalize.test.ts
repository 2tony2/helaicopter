import test from "node:test";
import assert from "node:assert/strict";

const {
  normalizeAnalytics,
  normalizeConversationEvaluations,
  normalizeConversationDetail,
  normalizeDatabaseStatus,
  normalizeEvaluationPrompts,
  normalizeOvernightOatsRuns,
  normalizeProjects,
  normalizeSubscriptionSettings,
  normalizeTasks,
} = await import(new URL("./normalize.ts", import.meta.url).href);
const {
  databaseStatusSchema,
} = await import(new URL("./schemas/database.ts", import.meta.url).href);
const {
  conversationEvaluationListSchema,
  evaluationPromptListSchema,
} = await import(new URL("./schemas/evaluations.ts", import.meta.url).href);
const {
  subscriptionSettingsSchema,
} = await import(new URL("./schemas/subscriptions.ts", import.meta.url).href);
const {
  conversation,
  conversationDags,
  getBaseUrl,
  projects,
  setBaseUrl,
  subagent,
} = await import(new URL("./endpoints.ts", import.meta.url).href);

async function importEndpointsWithApiBaseUrl(nextPublicApiBaseUrl?: string) {
  const previousValue = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (nextPublicApiBaseUrl === undefined) {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  } else {
    process.env.NEXT_PUBLIC_API_BASE_URL = nextPublicApiBaseUrl;
  }

  try {
    const moduleUrl = new URL(
      `./endpoints.ts?baseUrl=${encodeURIComponent(nextPublicApiBaseUrl ?? "unset")}&ts=${Date.now()}`,
      import.meta.url
    );
    return await import(moduleUrl.href);
  } finally {
    if (previousValue === undefined) {
      delete process.env.NEXT_PUBLIC_API_BASE_URL;
    } else {
      process.env.NEXT_PUBLIC_API_BASE_URL = previousValue;
    }
  }
}

test("invalid NEXT_PUBLIC_API_BASE_URL falls back to an empty configured base URL", async () => {
  const endpoints = await importEndpointsWithApiBaseUrl(" not-a-url ");

  assert.equal(endpoints.getBaseUrl(), "");
  assert.equal(endpoints.projects(), "/projects");
});

test("absolute NEXT_PUBLIC_API_BASE_URL values are trimmed and normalized", async () => {
  const endpoints = await importEndpointsWithApiBaseUrl(" https://api.example.test/// ");

  assert.equal(endpoints.getBaseUrl(), "https://api.example.test");
  assert.equal(endpoints.projects(), "https://api.example.test/projects");
});

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
  assert.equal(
    subagent("-Users-tony-Code-helaicopter", "session-123", "agent-1"),
    "https://api.example.test/conversations/-Users-tony-Code-helaicopter/session-123/subagents/agent-1"
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
    assert.equal(
      subagent("-Users-tony-Code-helaicopter", "session-123", "agent-1"),
      "http://localhost:30000/conversations/-Users-tony-Code-helaicopter/session-123/subagents/agent-1"
    );
  } finally {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: originalWindow,
    });
  }
});

test("setBaseUrl continues to normalize absolute URLs for explicit overrides", () => {
  setBaseUrl(" https://api.example.test/// ");

  assert.equal(getBaseUrl(), "https://api.example.test");
  assert.equal(projects(), "https://api.example.test/projects");
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
  assert.equal(normalized.rates.totalTokens.perDay, 20);
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
      frontend_cache: {
        key: "frontend_cache",
        label: "Frontend Short-Term Cache",
        engine: "In-process memory",
        role: "cache",
        availability: "ready",
        operational_status: "Warm in-process response cache",
        table_count: 0,
        load: [],
        tables: [],
      },
      sqlite: {
        key: "sqlite",
        label: "SQLite Metadata Store",
        engine: "SQLite",
        role: "metadata",
        availability: "ready",
        table_count: 4,
        load: [],
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
      duckdb: {
        key: "duckdb",
        label: "DuckDB Inspection Snapshot",
        engine: "DuckDB",
        role: "inspection",
        availability: "missing",
        table_count: 0,
        load: [],
        tables: [],
      },
      prefect_postgres: {
        key: "prefect_postgres",
        label: "Prefect Postgres",
        engine: "Postgres",
        role: "orchestration",
        availability: "ready",
        operational_status: "Prefect API responding",
        table_count: 0,
        load: [],
        tables: [],
      },
    },
  });

  assert.equal(normalized.startedAt, "2026-03-18T10:00:00Z");
  assert.equal(normalized.durationMs, 5000);
  assert.equal(normalized.runtime.analyticsReadBackend, "legacy");
  assert.equal(normalized.databases.frontendCache.key, "frontend_cache");
  assert.equal(normalized.databases.frontendCache.operationalStatus, "Warm in-process response cache");
  assert.equal(normalized.databases.sqlite.tableCount, 4);
  assert.equal(normalized.databases.sqlite.tables[0].rowCount, 3);
  assert.equal(normalized.databases.sqlite.tables[0].columns[0].defaultValue, null);
  assert.equal(normalized.databases.sqlite.tables[0].columns[0].isPrimaryKey, true);
  assert.equal(normalized.databases.duckdb.key, "duckdb");
  assert.equal(normalized.databases.prefectPostgres.key, "prefect_postgres");
});

test("normalizeDatabaseStatus still accepts legacy duckdb field names during transition", () => {
  const normalized = normalizeDatabaseStatus({
    status: "completed",
    refreshIntervalMinutes: 360,
    runtime: {
      analyticsReadBackend: "legacy",
      conversationSummaryReadBackend: "legacy",
    },
    databases: {
      sqlite: {
        key: "sqlite",
        label: "SQLite Metadata Store",
        engine: "SQLite",
        role: "metadata",
        availability: "ready",
        tableCount: 0,
        load: [],
        tables: [],
      },
      legacyDuckdb: {
        key: "duckdb",
        label: "DuckDB Inspection Snapshot",
        engine: "DuckDB",
        role: "inspection",
        availability: "ready",
        tableCount: 0,
        load: [],
        tables: [],
      },
    },
  });

  assert.equal(normalized.databases.duckdb.key, "duckdb");
});

test("evaluation prompt payload schemas parse accepted API shapes and reject silent fallbacks", () => {
  const parsed = evaluationPromptListSchema.parse([
    {
      prompt_id: "prompt-1",
      name: "Failure Sweep",
      description: "Inspect failures",
      prompt_text: "Look for recoverable errors.",
      is_default: false,
      created_at: "2026-03-18T10:00:00Z",
      updated_at: "2026-03-18T10:01:00Z",
    },
    {
      promptId: "prompt-2",
      name: "Default Review",
      description: null,
      promptText: "Use the existing fallback.",
      isDefault: true,
      createdAt: "2026-03-18T10:02:00Z",
      updatedAt: "2026-03-18T10:03:00Z",
    },
  ]);

  assert.equal(parsed.length, 2);
  assert.deepEqual(normalizeEvaluationPrompts(parsed), [
    {
      promptId: "prompt-1",
      name: "Failure Sweep",
      description: "Inspect failures",
      promptText: "Look for recoverable errors.",
      isDefault: false,
      createdAt: "2026-03-18T10:00:00Z",
      updatedAt: "2026-03-18T10:01:00Z",
    },
    {
      promptId: "prompt-2",
      name: "Default Review",
      description: null,
      promptText: "Use the existing fallback.",
      isDefault: true,
      createdAt: "2026-03-18T10:02:00Z",
      updatedAt: "2026-03-18T10:03:00Z",
    },
  ]);

  assert.throws(
    () =>
      evaluationPromptListSchema.parse([
        {
          prompt_id: "prompt-3",
          name: "Broken",
          prompt_text: "Would previously coerce to empty timestamps.",
          is_default: false,
          created_at: 123,
          updated_at: "2026-03-18T10:03:00Z",
        },
      ]),
    /created_at|createdAt/i
  );
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

test("conversation evaluation payload schemas parse accepted API shapes and reject silent fallbacks", () => {
  const parsed = conversationEvaluationListSchema.parse([
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
    {
      evaluationId: "evaluation-2",
      conversationId: "claude:session-2",
      promptId: null,
      provider: "claude",
      model: "sonnet",
      status: "completed",
      scope: "full",
      selectionInstruction: null,
      promptName: "Full Review",
      promptText: "Review everything.",
      reportMarkdown: "# Looks good",
      rawOutput: "raw",
      errorMessage: null,
      command: "claude run",
      createdAt: "2026-03-18T10:04:00Z",
      finishedAt: "2026-03-18T10:05:00Z",
      durationMs: 1000,
    },
  ]);

  assert.equal(parsed.length, 2);
  assert.equal(normalizeConversationEvaluations(parsed)[1].status, "completed");

  assert.throws(
    () =>
      conversationEvaluationListSchema.parse([
        {
          evaluation_id: "evaluation-3",
          conversation_id: "claude:session-3",
          prompt_id: "prompt-1",
          provider: "codex",
          model: "gpt-5",
          status: "queued",
          scope: "full",
          selection_instruction: null,
          prompt_name: "Queued Review",
          prompt_text: "Should fail.",
          report_markdown: null,
          raw_output: null,
          error_message: null,
          command: "codex exec --model gpt-5",
          created_at: "2026-03-18T10:06:00Z",
          finished_at: null,
          duration_ms: null,
        },
      ]),
    /status/i
  );
});

test("normalizeOvernightOatsRuns removes the frontend-only required evaluation field", () => {
  const runs = normalizeOvernightOatsRuns([
    {
      source: "overnight-oats",
      contractVersion: "oats-runtime-v1",
      runId: "run-1",
      runTitle: "Full Program Authoritative Analytics Overnight",
      repoRoot: "/Users/tony/Code/helaicopter",
      configPath: "/Users/tony/Code/helaicopter/.oats/config.toml",
      runSpecPath: "/Users/tony/Code/helaicopter/.oats/runs/run-1/spec.md",
      mode: "full-program",
      integrationBranch: "feature/full-program",
      taskPrTarget: "main",
      finalPrTarget: "main",
      status: "running",
      activeTaskId: "task-1",
      heartbeatAt: "2026-03-19T10:15:00Z",
      finishedAt: null,
      planner: {
        agent: "claude",
        role: "planner",
        command: ["codex"],
        cwd: "/Users/tony/Code/helaicopter",
        prompt: "Ship it",
        sessionId: "planner-session",
        startedAt: "2026-03-19T10:00:00Z",
        finishedAt: null,
      },
      tasks: [
        {
          taskId: "task-1",
          title: "Frontend simplification",
          dependsOn: [],
          status: "running",
          attempts: 1,
          invocation: null,
        },
      ],
      createdAt: "2026-03-19T10:00:00Z",
      lastUpdatedAt: "2026-03-19T10:15:00Z",
      isRunning: true,
      recordedAt: "2026-03-19T10:15:00Z",
      recordPath: "/Users/tony/Code/helaicopter/.oats/runs/run-1.json",
      dag: {
        nodes: [
          {
            id: "task-1",
            kind: "task",
            label: "Frontend simplification",
            role: "implementer",
            agent: "codex",
            status: "running",
            isActive: true,
            attempts: 1,
            lastHeartbeatAt: "2026-03-19T10:15:00Z",
            exitCode: null,
            timedOut: false,
            depth: 1,
          },
        ],
        edges: [],
        stats: {
          totalNodes: 1,
          totalEdges: 0,
          maxDepth: 1,
          maxBreadth: 1,
          rootCount: 1,
          providerBreakdown: { codex: 1 },
          timedOutCount: 0,
          activeCount: 1,
          pendingCount: 0,
          failedCount: 0,
          succeededCount: 0,
        },
      },
    },
  ]);

  assert.equal(runs[0].evaluation, undefined);
  assert.equal(runs[0].tasks[0].invocation, null);
  assert.equal(runs[0].dag.nodes[0].exitCode, undefined);
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

test("subscription settings schema parses provider records and rejects silent fallbacks", () => {
  const parsed = subscriptionSettingsSchema.parse({
    claude: {
      provider: "claude",
      has_subscription: false,
      monthly_cost: 123.45,
      updated_at: "2026-03-18T10:00:00Z",
    },
    codex: {
      provider: "codex",
      hasSubscription: true,
      monthlyCost: 200,
      updatedAt: "2026-03-18T10:00:00Z",
    },
  });

  assert.deepEqual(normalizeSubscriptionSettings(parsed), {
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

  assert.throws(
    () =>
      subscriptionSettingsSchema.parse({
        claude: {
          provider: "claude",
          has_subscription: false,
          monthly_cost: "123.45",
          updated_at: "2026-03-18T10:00:00Z",
        },
        codex: {
          provider: "codex",
          has_subscription: true,
          monthly_cost: 200,
          updated_at: "2026-03-18T10:00:00Z",
        },
      }),
    /monthly_cost|monthlyCost/i
  );
});

test("database status schema parses current backend shapes and rejects silent fallbacks", () => {
  const parsed = databaseStatusSchema.parse({
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
      frontend_cache: {
        key: "frontend_cache",
        label: "Frontend Short-Term Cache",
        engine: "In-process memory",
        role: "cache",
        availability: "ready",
        table_count: 0,
        load: [],
        tables: [],
      },
      sqlite: {
        key: "sqlite",
        label: "SQLite Metadata Store",
        engine: "SQLite",
        role: "metadata",
        availability: "ready",
        table_count: 0,
        load: [],
        tables: [],
      },
      legacyDuckdb: {
        key: "duckdb",
        label: "DuckDB Inspection Snapshot",
        engine: "DuckDB",
        role: "inspection",
        availability: "missing",
        table_count: 0,
        load: [],
        tables: [],
      },
      prefect_postgres: {
        key: "prefect_postgres",
        label: "Prefect Postgres",
        engine: "Postgres",
        role: "orchestration",
        availability: "ready",
        table_count: 0,
        load: [],
        tables: [],
      },
    },
  });

  assert.equal(normalizeDatabaseStatus(parsed).databases.duckdb.key, "duckdb");

  assert.throws(
    () =>
      databaseStatusSchema.parse({
        status: "failed",
        refresh_interval_minutes: 360,
        runtime: {
          analytics_read_backend: "legacy",
          conversation_summary_read_backend: "legacy",
        },
        databases: {
          frontend_cache: {
            key: "frontend_cache",
            label: "Frontend Short-Term Cache",
            engine: "In-process memory",
            role: "cache",
            availability: "ready",
            table_count: "zero",
            load: [],
            tables: [],
          },
          sqlite: {
            key: "sqlite",
            label: "SQLite Metadata Store",
            engine: "SQLite",
            role: "metadata",
            availability: "ready",
            table_count: 0,
            load: [],
            tables: [],
          },
          duckdb: {
            key: "duckdb",
            label: "DuckDB Inspection Snapshot",
            engine: "DuckDB",
            role: "inspection",
            availability: "missing",
            table_count: 0,
            load: [],
            tables: [],
          },
          prefect_postgres: {
            key: "prefect_postgres",
            label: "Prefect Postgres",
            engine: "Postgres",
            role: "orchestration",
            availability: "ready",
            table_count: 0,
            load: [],
            tables: [],
          },
        },
      }),
    /table_count|tableCount/i
  );
});
