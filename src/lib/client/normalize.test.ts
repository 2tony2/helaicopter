import test from "node:test";
import assert from "node:assert/strict";

async function getNormalize() {
  return import(new URL("./normalize.ts", import.meta.url).href);
}

async function getEndpoints() {
  return import(new URL("./endpoints.ts", import.meta.url).href);
}

async function getConversationsSchema() {
  return import(new URL("./schemas/conversations.ts", import.meta.url).href);
}

async function getDatabaseSchema() {
  return import(new URL("./schemas/database.ts", import.meta.url).href);
}

async function getEvaluationsSchema() {
  return import(new URL("./schemas/evaluations.ts", import.meta.url).href);
}

async function getSubscriptionsSchema() {
  return import(new URL("./schemas/subscriptions.ts", import.meta.url).href);
}

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
    const endpoints = await import(moduleUrl.href);
    // Explicitly apply the intended base URL to ensure tests don't depend on loader env propagation.
    endpoints.setBaseUrl(nextPublicApiBaseUrl ?? "");
    return endpoints;
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

test("endpoint builders target FastAPI routes without the Next /api prefix", async () => {
  const { setBaseUrl, projects, conversation, conversationDags, subagent, conversationByRef } = await getEndpoints();
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
  assert.equal(
    conversationByRef("review-the-backend-rollout--claude-claude-session-1"),
    "https://api.example.test/conversations/by-ref/review-the-backend-rollout--claude-claude-session-1"
  );
});

test("endpoint builders infer the local FastAPI origin when the frontend runs on localhost", async () => {
  const { setBaseUrl, projects, conversation, conversationDags, subagent, conversationByRef } = await getEndpoints();
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
    assert.equal(
      conversationByRef("review-the-backend-rollout--claude-claude-session-1"),
      "http://localhost:30000/conversations/by-ref/review-the-backend-rollout--claude-claude-session-1"
    );
  } finally {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: originalWindow,
    });
  }
});

test("endpoint builders append parent_session_id only when the caller provides parentSessionId", async () => {
  const { setBaseUrl, conversation, conversationDag, conversationEvaluations, tasks } = await getEndpoints();
  setBaseUrl("https://api.example.test/");

  assert.equal(
    conversation("-Users-tony-Code-helaicopter", "claude-agent-1"),
    "https://api.example.test/conversations/-Users-tony-Code-helaicopter/claude-agent-1"
  );
  assert.equal(
    conversation("-Users-tony-Code-helaicopter", "claude-agent-1", {
      parentSessionId: "claude-session-1",
    }),
    "https://api.example.test/conversations/-Users-tony-Code-helaicopter/claude-agent-1?parent_session_id=claude-session-1"
  );

  assert.equal(
    conversationDag("-Users-tony-Code-helaicopter", "claude-agent-1"),
    "https://api.example.test/conversations/-Users-tony-Code-helaicopter/claude-agent-1/dag"
  );
  assert.equal(
    conversationDag("-Users-tony-Code-helaicopter", "claude-agent-1", {
      parentSessionId: "claude-session-1",
    }),
    "https://api.example.test/conversations/-Users-tony-Code-helaicopter/claude-agent-1/dag?parent_session_id=claude-session-1"
  );

  assert.equal(
    conversationEvaluations("-Users-tony-Code-helaicopter", "claude-agent-1"),
    "https://api.example.test/conversations/-Users-tony-Code-helaicopter/claude-agent-1/evaluations"
  );
  assert.equal(
    conversationEvaluations("-Users-tony-Code-helaicopter", "claude-agent-1", {
      parentSessionId: "claude-session-1",
    }),
    "https://api.example.test/conversations/-Users-tony-Code-helaicopter/claude-agent-1/evaluations?parent_session_id=claude-session-1"
  );

  assert.equal(tasks("claude-agent-1"), "https://api.example.test/tasks/claude-agent-1");
  assert.equal(
    tasks("claude-agent-1", { parentSessionId: "claude-session-1" }),
    "https://api.example.test/tasks/claude-agent-1?parent_session_id=claude-session-1"
  );
});

test("normalizeConversations preserves canonical conversation refs from summary payloads", async () => {
  const { normalizeConversations } = await getNormalize();
  const normalized = normalizeConversations([
    {
      session_id: "claude-session-1",
      project_path: "-Users-tony-Code-helaicopter",
      project_name: "helaicopter",
      route_slug: "review-the-backend-rollout",
      conversation_ref: "review-the-backend-rollout--claude-claude-session-1",
      thread_type: "main",
      first_message: "Review the backend rollout",
      timestamp: 1763000000000,
      created_at: 1763000000000,
      last_updated_at: 1763000001000,
      is_running: false,
    },
  ]);

  assert.equal(normalized[0].routeSlug, "review-the-backend-rollout");
  assert.equal(
    normalized[0].conversationRef,
    "review-the-backend-rollout--claude-claude-session-1"
  );
});

test("setBaseUrl continues to normalize absolute URLs for explicit overrides", async () => {
  const { setBaseUrl, getBaseUrl, projects } = await getEndpoints();
  setBaseUrl(" https://api.example.test/// ");

  assert.equal(getBaseUrl(), "https://api.example.test");
  assert.equal(projects(), "https://api.example.test/projects");
});

test("normalizeProjects maps FastAPI project payloads to frontend camelCase types", async () => {
  const { normalizeProjects } = await getNormalize();
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

test("normalizeProjects also accepts existing Next.js camelCase payloads", async () => {
  const { normalizeProjects } = await getNormalize();
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

test("conversation summary payload schemas parse accepted API shapes and reject silent fallbacks", async () => {
  const { conversationSummaryListSchema } = await getConversationsSchema();
  const { normalizeConversations } = await getNormalize();
  const parsed = conversationSummaryListSchema.parse([
    {
      session_id: "session-123",
      project_path: "-Users-tony-Code-helaicopter",
      project_name: "helaicopter",
      route_slug: "ship-the-patch",
      conversation_ref: "ship-the-patch--claude-session-123",
      thread_type: "main",
      first_message: "Ship the patch",
      timestamp: 1763000002000,
      created_at: 1763000000000,
      last_updated_at: 1763000001000,
      is_running: false,
      message_count: 14,
      model: "gpt-5",
      total_input_tokens: 120,
      total_output_tokens: 240,
      total_cache_creation_tokens: 30,
      total_cache_read_tokens: 40,
      tool_use_count: 4,
      failed_tool_call_count: 1,
      tool_breakdown: { Bash: 3, Read: 1 },
      subagent_count: 2,
      subagent_type_breakdown: { reviewer: 1, implementer: 1 },
      task_count: 3,
      git_branch: "feature/zod",
      reasoning_effort: "medium",
      speed: "fast",
      total_reasoning_tokens: 90,
    },
    {
      sessionId: "session-456",
      projectPath: "codex:-Users-tony-Code-helaicopter",
      projectName: "Codex/helaicopter",
      routeSlug: "investigate-the-failing-tests",
      conversationRef: "investigate-the-failing-tests--codex-session-456",
      threadType: "subagent",
      firstMessage: "Investigate the failing tests",
      timestamp: 1763000003000,
      createdAt: 1763000002000,
      lastUpdatedAt: 1763000002500,
      isRunning: true,
      messageCount: 5,
      model: null,
      totalInputTokens: 10,
      totalOutputTokens: 20,
      totalCacheCreationTokens: 0,
      totalCacheReadTokens: 0,
      toolUseCount: 1,
      failedToolCallCount: 0,
      toolBreakdown: {},
      subagentCount: 0,
      subagentTypeBreakdown: {},
      taskCount: 0,
      gitBranch: null,
      reasoningEffort: null,
      speed: null,
      totalReasoningTokens: null,
    },
  ]);

  assert.equal(parsed.length, 2);
  assert.equal(normalizeConversations(parsed)[0].toolBreakdown.Bash, 3);
  assert.equal(normalizeConversations(parsed)[1].threadType, "subagent");

  assert.throws(
    () =>
      conversationSummaryListSchema.parse([
        {
          session_id: "session-789",
          project_path: "-Users-tony-Code-helaicopter",
          project_name: "helaicopter",
          thread_type: "queued",
          first_message: "Broken payload",
          timestamp: "1763000004000",
          created_at: 1763000000000,
          last_updated_at: 1763000001000,
          is_running: false,
          message_count: 14,
          model: "gpt-5",
          total_input_tokens: 120,
          total_output_tokens: 240,
          total_cache_creation_tokens: 30,
          total_cache_read_tokens: 40,
          tool_use_count: 4,
          failed_tool_call_count: 1,
          tool_breakdown: { Bash: 3 },
          subagent_count: 2,
          subagent_type_breakdown: { reviewer: 1 },
          task_count: 3,
          git_branch: "feature/zod",
          reasoning_effort: "medium",
          speed: "fast",
          total_reasoning_tokens: 90,
        },
      ]),
    /thread_type|threadType|timestamp/i
  );
});

test("provider schemas accept openclaw", async () => {
  const shared = await import(new URL("./schemas/shared.ts", import.meta.url).href);
  assert.equal(shared.providerSchema.parse("openclaw"), "openclaw");
  assert.equal(shared.providerFilterSchema.parse("openclaw"), "openclaw");
});

test("normalizeConversations preserves openclaw providers from summary payloads", async () => {
  const { normalizeConversations } = await getNormalize();
  const normalized = normalizeConversations([
    {
      session_id: "openclaw-session-1",
      project_path: "-Users-tony-Code-helaicopter",
      project_name: "helaicopter",
      route_slug: "review-openclaw-rollout",
      conversation_ref: "review-openclaw-rollout--openclaw-openclaw-session-1",
      thread_type: "main",
      provider: "openclaw",
      first_message: "Validate OpenClaw provider handling",
      timestamp: 1763000004000,
      created_at: 1763000003000,
      last_updated_at: 1763000003500,
      is_running: false,
      message_count: 2,
      model: "openclaw-v1",
      total_input_tokens: 10,
      total_output_tokens: 20,
      total_cache_creation_tokens: 0,
      total_cache_read_tokens: 0,
      tool_use_count: 0,
      failed_tool_call_count: 0,
      tool_breakdown: {},
      subagent_count: 0,
      subagent_type_breakdown: {},
      task_count: 0,
      git_branch: null,
      reasoning_effort: null,
      speed: null,
      total_reasoning_tokens: null,
    },
  ]);

  assert.equal(normalized[0].provider, "openclaw");
});

test("normalizePlan rejects unknown providers instead of coercing them to claude", async () => {
  const { normalizePlan } = await getNormalize();
  assert.throws(
    () =>
      normalizePlan({
        id: "plan-unknown-provider",
        slug: "plan-unknown-provider",
        title: "Unknown provider",
        content: "content",
        provider: "mystery",
        timestamp: 1763000004000,
      }),
    /Invalid option/i
  );
});

test("normalizeConversationDetail preserves token usage semantics expected by the viewer", async () => {
  const { normalizeConversationDetail } = await getNormalize();
  const normalized = normalizeConversationDetail({
    session_id: "session-123",
    project_path: "-Users-tony-Code-helaicopter",
    route_slug: "review-the-backend-rollout",
    conversation_ref: "review-the-backend-rollout--claude-session-123",
    thread_type: "main",
    provider: "openclaw",
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
        provider: "openclaw",
        timestamp: 1763000000000,
        session_id: "session-123",
        project_path: "-Users-tony-Code-helaicopter",
        route_slug: "review-the-backend-rollout",
        conversation_ref: "review-the-backend-rollout--claude-session-123",
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
        route_slug: "inspect-the-dag-graph",
        conversation_ref: "inspect-the-dag-graph--claude-agent-1",
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
  assert.equal(normalized.provider, "openclaw");
  assert.equal(normalized.routeSlug, "review-the-backend-rollout");
  assert.equal(normalized.conversationRef, "review-the-backend-rollout--claude-session-123");
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
  const firstBlock = normalized.messages[0].blocks[0];
  assert.equal(firstBlock.type, "tool_call");
  if (firstBlock.type !== "tool_call") {
    throw new Error("Expected the first block to be a tool call.");
  }
  assert.equal(firstBlock.toolUseId, "tool-1");
  assert.equal(normalized.plans[0].provider, "openclaw");
  assert.equal(normalized.plans[0].sessionId, "session-123");
  assert.equal(normalized.plans[0].routeSlug, "review-the-backend-rollout");
  assert.equal(
    normalized.plans[0].conversationRef,
    "review-the-backend-rollout--claude-session-123"
  );
  assert.equal(normalized.subagents[0].agentId, "agent-1");
  assert.equal(normalized.subagents[0].routeSlug, "inspect-the-dag-graph");
  assert.equal(
    normalized.subagents[0].conversationRef,
    "inspect-the-dag-graph--claude-agent-1"
  );
  assert.equal(normalized.contextAnalytics.buckets[0].cacheWriteTokens, 3);
  assert.equal(normalized.contextWindow.peakContextWindow, 44);
});

test("normalizeConversationDetail preserves OpenClaw provider detail payloads", async () => {
  const { normalizeConversationDetail } = await getNormalize();
  const { conversationDetailSchema } = await getConversationsSchema();
  const parsed = conversationDetailSchema.parse({
    session_id: "openclaw-session-1",
    project_path: "openclaw:agent:main",
    route_slug: "review-openclaw-rollout",
    conversation_ref: "review-openclaw-rollout--openclaw-openclaw:agent:main::openclaw-session-1",
    provider: "openclaw",
    created_at: 1763000000000,
    last_updated_at: 1763000001000,
    is_running: false,
    messages: [],
    plans: [],
    total_usage: {
      input_tokens: 100,
      output_tokens: 200,
      cache_creation_tokens: 30,
      cache_read_tokens: 40,
    },
    start_time: 1763000000000,
    end_time: 1763000001000,
    subagents: [],
    context_analytics: {
      buckets: [],
      steps: [],
    },
    context_window: {
      peak_context_window: 44,
      api_calls: 2,
      cumulative_tokens: 300,
    },
    provider_detail: {
      kind: "openclaw",
      openclaw: {
        artifact_inventory: {
          live_transcript: {
            path: "/Users/tony/.openclaw/agents/main/sessions/openclaw-session-1.jsonl",
            status: "live",
            canonical_session_id: "openclaw-session-1",
          },
          attached_archives: [
            {
              kind: "reset_archive",
              path: "/Users/tony/.openclaw/agents/main/sessions/openclaw-session-1.jsonl.reset.2026-03-22T03-00-11.497Z",
            },
          ],
        },
        session_store: {
          sessionKey: "agent:main:main",
          skills: {
            prompt: "Follow the OpenClaw rollout checklist",
          },
        },
        skills: {
          prompt: "Follow the OpenClaw rollout checklist",
          declared: [{ name: "planner", source: "builtin" }],
        },
        system_prompt: {
          workspace_dir: "/Users/tony/Code/helaicopter",
          sandbox_mode: "workspace-write",
        },
        transcript_diagnostics: {
          event_types: {
            custom_message: 1,
            branch_summary: 1,
          },
        },
        usage_reconciliation: {
          transcript_total_tokens: 195,
          store_total_tokens: 275,
        },
        memory_store: {
          path: "/Users/tony/.openclaw/memory/main.sqlite",
          tables: ["chunks", "files"],
          counts: {
            files: 2,
            chunks: 3,
          },
          workspace_link: {
            workspace_dir: "/Users/tony/Code/helaicopter",
            matched_prefix: "/Users/tony/Code/helaicopter",
            confidence: "exact",
          },
        },
        raw: {
          session_store_entry: {
            sessionId: "openclaw-session-1",
          },
        },
      },
    },
  });

  const normalized = normalizeConversationDetail(parsed);

  assert.equal(normalized.providerDetail?.kind, "openclaw");
  assert.equal(
    normalized.providerDetail?.openclaw.artifactInventory.liveTranscript?.status,
    "live"
  );
  assert.equal(
    normalized.providerDetail?.openclaw.artifactInventory.attachedArchives[0]?.kind,
    "reset_archive"
  );
  assert.equal(
    normalized.providerDetail?.openclaw.skills?.declared?.[0]?.name,
    "planner"
  );
  assert.equal(
    normalized.providerDetail?.openclaw.systemPrompt?.workspaceDir,
    "/Users/tony/Code/helaicopter"
  );
  assert.equal(
    normalized.providerDetail?.openclaw.usageReconciliation?.storeTotalTokens,
    275
  );
  assert.equal(
    normalized.providerDetail?.openclaw.memoryStore?.workspaceLink?.confidence,
    "exact"
  );
  assert.equal(
    (normalized.providerDetail?.openclaw.raw?.session_store_entry as { sessionId?: string } | undefined)
      ?.sessionId,
    "openclaw-session-1"
  );
});

test("normalizeConversationDetail omits provider detail for non-OpenClaw payloads", async () => {
  const { normalizeConversationDetail } = await getNormalize();
  const normalized = normalizeConversationDetail({
    session_id: "claude-session-1",
    project_path: "-Users-tony-Code-helaicopter",
    provider: "claude",
    created_at: 1763000000000,
    last_updated_at: 1763000001000,
    is_running: false,
    messages: [],
    plans: [],
    total_usage: {
      input_tokens: 1,
      output_tokens: 2,
      cache_creation_tokens: 0,
      cache_read_tokens: 0,
    },
    start_time: 1763000000000,
    end_time: 1763000001000,
    subagents: [],
    context_analytics: { buckets: [], steps: [] },
    context_window: {
      peak_context_window: 0,
      api_calls: 0,
      cumulative_tokens: 0,
    },
  });

  assert.equal(normalized.providerDetail, undefined);
});

test("normalizeConversationDetail tolerates sparse OpenClaw provider detail payloads", async () => {
  const { normalizeConversationDetail } = await getNormalize();
  const normalized = normalizeConversationDetail({
    session_id: "openclaw-session-2",
    project_path: "openclaw:agent:main",
    provider: "openclaw",
    created_at: 1763000000000,
    last_updated_at: 1763000001000,
    is_running: false,
    messages: [],
    plans: [],
    total_usage: {
      input_tokens: 1,
      output_tokens: 2,
      cache_creation_tokens: 0,
      cache_read_tokens: 0,
    },
    start_time: 1763000000000,
    end_time: 1763000001000,
    subagents: [],
    context_analytics: { buckets: [], steps: [] },
    context_window: {
      peak_context_window: 0,
      api_calls: 0,
      cumulative_tokens: 0,
    },
    provider_detail: {
      kind: "openclaw",
      openclaw: {
        artifact_inventory: {},
      },
    },
  });

  assert.equal(normalized.providerDetail?.kind, "openclaw");
  assert.deepEqual(normalized.providerDetail?.openclaw.artifactInventory.attachedArchives, []);
  assert.equal(normalized.providerDetail?.openclaw.memoryStore, undefined);
});

test("normalizeConversationDetail still accepts camelCase detail payloads during rollout", async () => {
  const { normalizeConversationDetail } = await getNormalize();
  const { conversationDetailSchema } = await getConversationsSchema();
  const parsed = conversationDetailSchema.parse({
    sessionId: "openclaw-session-3",
    projectPath: "openclaw:agent:main",
    provider: "openclaw",
    routeSlug: "camel-openclaw-rollout",
    conversationRef: "camel-openclaw-rollout--openclaw-openclaw:agent:main::openclaw-session-3",
    threadType: "main",
    createdAt: 1763000000000,
    lastUpdatedAt: 1763000001000,
    isRunning: false,
    messages: [
      {
        id: "camel-message-1",
        role: "assistant",
        timestamp: 1763000000000,
        blocks: [
          {
            type: "tool_call",
            toolUseId: "tool-camel-1",
            toolName: "Shell",
            input: {},
            result: "stdout",
            isError: false,
          },
        ],
        usage: {
          inputTokens: 5,
          outputTokens: 6,
          cacheCreationTokens: 1,
          cacheReadTokens: 2,
        },
        reasoningTokens: 7,
      },
    ],
    plans: [
      {
        id: "camel-plan-1",
        slug: "camel-plan-1",
        title: "Camel plan",
        preview: "Preview",
        content: "Content",
        provider: "openclaw",
        timestamp: 1763000000000,
        sessionId: "openclaw-session-3",
        projectPath: "openclaw:agent:main",
        routeSlug: "camel-openclaw-rollout",
        conversationRef:
          "camel-openclaw-rollout--openclaw-openclaw:agent:main::openclaw-session-3",
        sourcePath: "/tmp/camel-plan.md",
      },
    ],
    totalUsage: {
      inputTokens: 3,
      outputTokens: 4,
      cacheCreationTokens: 0,
      cacheReadTokens: 0,
    },
    startTime: 1763000000000,
    endTime: 1763000001000,
    subagents: [
      {
        agentId: "camel-agent-1",
        hasFile: true,
        projectPath: "openclaw:agent:main",
        sessionId: "camel-agent-1",
        routeSlug: "camel-agent-route",
        conversationRef: "camel-agent-route--openclaw-openclaw:agent:main::camel-agent-1",
      },
    ],
    contextAnalytics: {
      buckets: [
        {
          label: "conversation",
          category: "conversation",
          inputTokens: 1,
          outputTokens: 2,
          cacheWriteTokens: 3,
          cacheReadTokens: 4,
          totalTokens: 10,
          calls: 1,
        },
      ],
      steps: [
        {
          messageId: "camel-message-1",
          index: 0,
          role: "assistant",
          label: "conversation",
          category: "conversation",
          timestamp: 1763000000000,
          inputTokens: 1,
          outputTokens: 2,
          cacheWriteTokens: 3,
          cacheReadTokens: 4,
          totalTokens: 10,
        },
      ],
    },
    contextWindow: {
      peakContextWindow: 9,
      apiCalls: 2,
      cumulativeTokens: 30,
    },
    providerDetail: {
      kind: "openclaw",
      openclaw: {
        artifactInventory: {
          attachedArchives: [],
        },
        systemPrompt: {
          workspaceDir: "/Users/tony/Code/helaicopter",
        },
        raw: {
          session_store_entry: {
            sessionId: "openclaw-session-3",
          },
        },
      },
    },
  });
  const normalized = normalizeConversationDetail(parsed);

  assert.equal(normalized.sessionId, "openclaw-session-3");
  assert.equal(normalized.routeSlug, "camel-openclaw-rollout");
  assert.equal(
    normalized.providerDetail?.openclaw.systemPrompt?.workspaceDir,
    "/Users/tony/Code/helaicopter"
  );
  assert.equal(
    (normalized.providerDetail?.openclaw.raw?.session_store_entry as { sessionId?: string } | undefined)
      ?.sessionId,
    "openclaw-session-3"
  );
  assert.equal(normalized.messages[0]?.usage?.cache_creation_input_tokens, 1);
  assert.equal(normalized.messages[0]?.reasoningTokens, 7);
  assert.equal(normalized.plans[0]?.sourcePath, "/tmp/camel-plan.md");
  assert.equal(normalized.subagents[0]?.agentId, "camel-agent-1");
  assert.equal(normalized.contextAnalytics.buckets[0]?.cacheWriteTokens, 3);
  assert.equal(normalized.contextWindow.peakContextWindow, 9);
});

test("normalizeConversationDetail preserves standalone tool roles", async () => {
  const { normalizeConversationDetail } = await getNormalize();
  const normalized = normalizeConversationDetail({
    session_id: "tool-role-session",
    project_path: "openclaw:agent:main",
    created_at: 1763000000000,
    last_updated_at: 1763000001000,
    is_running: false,
    messages: [
      {
        id: "tool-msg-1",
        role: "tool",
        timestamp: 1763000000000,
        blocks: [
          {
            type: "tool_call",
            tool_use_id: "tool-1",
            tool_name: "Shell",
            input: {},
            result: "stdout",
            is_error: false,
          },
        ],
      },
    ],
    plans: [],
    total_usage: {
      input_tokens: 0,
      output_tokens: 0,
      cache_creation_tokens: 0,
      cache_read_tokens: 0,
    },
    start_time: 1763000000000,
    end_time: 1763000001000,
    subagents: [],
    context_analytics: { buckets: [], steps: [] },
  });

  assert.equal(normalized.messages[0].role, "tool");
});

test("normalizeConversationDag preserves null paths for unresolved child routes", async () => {
  const { normalizeConversationDag } = await getNormalize();
  const normalized = normalizeConversationDag({
    project_path: "-Users-tony-Code-helaicopter",
    root_session_id: "claude-session-1",
    nodes: [
      {
        id: "node-1",
        session_id: "claude-agent-missing",
        parent_session_id: "claude-session-1",
        project_path: "-Users-tony-Code-helaicopter",
        label: "Missing child",
        thread_type: "subagent",
        has_transcript: false,
        timestamp: 1763000000000,
        path: null,
        is_root: false,
      },
    ],
    edges: [],
    stats: {
      total_nodes: 1,
      total_edges: 0,
      total_subagent_nodes: 1,
      max_depth: 1,
      max_breadth: 1,
      leaf_count: 1,
      root_subagent_count: 0,
      total_messages: 0,
      total_tokens: 0,
    },
  });

  assert.equal(normalized.nodes[0].path, null);
});

test("normalizePlan preserves canonical conversation link fields", async () => {
  const { normalizePlan } = await getNormalize();
  const normalized = normalizePlan({
    id: "plan-1",
    slug: "claude-session-rollout",
    title: "Claude Session Rollout",
    content: "# Rollout",
    provider: "openclaw",
    timestamp: 1763000000000,
    session_id: "claude-session-1",
    project_path: "-Users-tony-Code-helaicopter",
    route_slug: "review-the-plan-panel",
    conversation_ref: "review-the-plan-panel--claude-claude-session-1",
  });

  assert.equal(normalized.provider, "openclaw");
  assert.equal(normalized.routeSlug, "review-the-plan-panel");
  assert.equal(
    normalized.conversationRef,
    "review-the-plan-panel--claude-claude-session-1"
  );
});

test("normalizeConversationRouteResolution maps resolver payloads to frontend camelCase types", async () => {
  const { normalizeConversationRouteResolution } = await getNormalize();
  const normalized = normalizeConversationRouteResolution({
    conversation_ref: "inspect-the-dag-graph--claude-claude-agent-1",
    route_slug: "inspect-the-dag-graph",
    project_path: "-Users-tony-Code-helaicopter",
    session_id: "claude-agent-1",
    thread_type: "subagent",
    parent_session_id: "claude-session-1",
  });

  assert.deepEqual(normalized, {
    conversationRef: "inspect-the-dag-graph--claude-claude-agent-1",
    routeSlug: "inspect-the-dag-graph",
    projectPath: "-Users-tony-Code-helaicopter",
    sessionId: "claude-agent-1",
    threadType: "subagent",
    parentSessionId: "claude-session-1",
  });
});

test("normalizeAnalytics accepts existing Next.js camelCase payloads", async () => {
  const { normalizeAnalytics } = await getNormalize();
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

test("normalizeTasks unwraps the FastAPI task envelope for the existing viewer", async () => {
  const { normalizeTasks } = await getNormalize();
  assert.deepEqual(
    normalizeTasks({
      session_id: "session-123",
      tasks: [{ taskId: "T017", title: "Frontend cutover" }],
    }),
    [{ taskId: "T017", title: "Frontend cutover" }]
  );
});

test("normalizeDatabaseStatus tolerates snake_case payloads for refresh responses", async () => {
  const { normalizeDatabaseStatus } = await getNormalize();
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

test("normalizeDatabaseStatus still accepts legacy duckdb field names during transition", async () => {
  const { normalizeDatabaseStatus } = await getNormalize();
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

test("evaluation prompt payload schemas parse accepted API shapes and reject silent fallbacks", async () => {
  const { evaluationPromptListSchema } = await getEvaluationsSchema();
  const { normalizeEvaluationPrompts } = await getNormalize();
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

test("normalizeEvaluationPrompts and normalizeConversationEvaluations map prompt and job records", async () => {
  const { normalizeEvaluationPrompts, normalizeConversationEvaluations } = await getNormalize();
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

test("conversation evaluation payload schemas parse accepted API shapes and reject silent fallbacks", async () => {
  const { conversationEvaluationListSchema } = await getEvaluationsSchema();
  const { normalizeConversationEvaluations } = await getNormalize();
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

test("normalizeOvernightOatsRuns removes the frontend-only required evaluation field", async () => {
  const { normalizeOvernightOatsRuns } = await getNormalize();
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

test("normalizeOvernightOatsRuns preserves stacked PR orchestration state", async () => {
  const { normalizeOvernightOatsRuns } = await getNormalize();
  const runs = normalizeOvernightOatsRuns([
    {
      source: "overnight-oats",
      contract_version: "oats-runtime-v2",
      run_id: "run-2",
      run_title: "Stacked PR rollout",
      repo_root: "/Users/tony/Code/helaicopter",
      config_path: "/Users/tony/Code/helaicopter/.oats/config.toml",
      run_spec_path: "/Users/tony/Code/helaicopter/.oats/runs/run-2/spec.md",
      mode: "full-program",
      integration_branch: "oats/overnight/runtime-facts",
      task_pr_target: "oats/overnight/runtime-facts",
      final_pr_target: "main",
      status: "running",
      stack_status: "awaiting_task_merge",
      feature_branch: {
        name: "oats/overnight/runtime-facts",
        base_branch: "main",
      },
      final_pr: {
        number: 42,
        url: "https://github.com/example/repo/pull/42",
        state: "open",
        review_gate_status: "awaiting_human",
        base_branch: "main",
        head_branch: "oats/overnight/runtime-facts",
        checks_summary: {
          total: 5,
          passing: 5,
        },
        snapshot_source: "github",
        last_refreshed_at: "2026-03-20T09:15:00Z",
        is_stale: false,
      },
      operation_history: [
        {
          kind: "refresh",
          status: "succeeded",
          session_id: "refresh-session",
          started_at: "2026-03-20T09:10:00Z",
          finished_at: "2026-03-20T09:10:30Z",
          details: {
            merged_prs: 1,
          },
        },
      ],
      active_task_id: "task-tests",
      heartbeat_at: "2026-03-20T09:15:00Z",
      finished_at: null,
      planner: null,
      tasks: [
        {
          task_id: "task-api",
          title: "Implement route",
          depends_on: [],
          parent_branch: "oats/overnight/runtime-facts",
          status: "succeeded",
          attempts: 1,
          task_pr: {
            number: 11,
            url: "https://github.com/example/repo/pull/11",
            state: "merged",
            merge_gate_status: "merged",
            base_branch: "oats/overnight/runtime-facts",
            head_branch: "oats/task/task-api",
            mergeability: "mergeable",
            checks_summary: {
              total: 4,
              passing: 4,
            },
            review_summary: {
              blocking_state: "clear",
              approvals: 1,
              changes_requested: 0,
            },
            snapshot_source: "github",
            last_refreshed_at: "2026-03-20T09:15:00Z",
            is_stale: false,
          },
          operation_history: [
            {
              kind: "pr_merge",
              status: "succeeded",
              session_id: "merge-session",
              started_at: "2026-03-20T09:00:00Z",
              finished_at: "2026-03-20T09:01:00Z",
              details: {
                merge_commit_sha: "abc123",
              },
            },
          ],
          invocation: null,
        },
        {
          task_id: "task-tests",
          title: "Patch UI",
          depends_on: ["task-api"],
          parent_branch: "oats/task/task-api",
          status: "blocked",
          attempts: 2,
          task_pr: {
            number: 12,
            state: "open",
            merge_gate_status: "awaiting_checks",
            base_branch: "oats/task/task-api",
            head_branch: "oats/task/task-tests",
            mergeability: "unknown",
            checks_summary: {
              total: 2,
              passing: 1,
              failing: 1,
            },
            review_summary: {
              blocking_state: "commented",
              approvals: 0,
              changes_requested: 0,
            },
            snapshot_source: "github",
            last_refreshed_at: "2026-03-20T09:15:00Z",
            is_stale: true,
          },
          operation_history: [
            {
              kind: "conflict_resolution",
              status: "started",
              session_id: "resolver-session",
              started_at: "2026-03-20T09:12:00Z",
              finished_at: null,
              details: {
                attempt: 1,
              },
            },
          ],
          invocation: null,
        },
      ],
      created_at: "2026-03-20T08:45:00Z",
      last_updated_at: "2026-03-20T09:15:00Z",
      is_running: true,
      recorded_at: "2026-03-20T09:15:00Z",
      record_path: "/Users/tony/Code/helaicopter/.oats/runs/run-2.json",
      dag: {
        nodes: [],
        edges: [],
        stats: {
          total_nodes: 0,
          total_edges: 0,
          max_depth: 0,
          max_breadth: 0,
          root_count: 0,
          provider_breakdown: {},
          timed_out_count: 0,
          active_count: 0,
          pending_count: 0,
          failed_count: 0,
          succeeded_count: 0,
        },
      },
    },
  ]);

  assert.equal(runs[0].contractVersion, "oats-runtime-v2");
  assert.equal(runs[0].stackStatus, "awaiting_task_merge");
  assert.equal(runs[0].featureBranch?.name, "oats/overnight/runtime-facts");
  assert.equal(runs[0].finalPr?.reviewGateStatus, "awaiting_human");
  assert.equal(runs[0].operationHistory[0].sessionId, "refresh-session");
  assert.equal(runs[0].tasks[0].parentBranch, "oats/overnight/runtime-facts");
  assert.equal(runs[0].tasks[0].taskPr?.mergeGateStatus, "merged");
  assert.equal(runs[0].tasks[0].taskPr?.reviewSummary?.approvals, 1);
  assert.equal(runs[0].tasks[1].taskPr?.isStale, true);
  assert.equal(runs[0].tasks[1].operationHistory[0].kind, "conflict_resolution");
});

test("normalizeSubscriptionSettings maps provider records for analytics settings", async () => {
  const { normalizeSubscriptionSettings } = await getNormalize();
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

test("subscription settings schema parses provider records and rejects silent fallbacks", async () => {
  const { subscriptionSettingsSchema } = await getSubscriptionsSchema();
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

  const { normalizeSubscriptionSettings } = await getNormalize();
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

test("database status schema parses current backend shapes and rejects silent fallbacks", async () => {
  const { databaseStatusSchema } = await getDatabaseSchema();
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

  const { normalizeDatabaseStatus } = await getNormalize();
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
