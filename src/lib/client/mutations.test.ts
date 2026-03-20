import test from "node:test";
import assert from "node:assert/strict";

const {
  createConversationEvaluation,
  createEvaluationPrompt,
  refreshDatabase,
  saveSubscriptionSettings,
} = await import(new URL("./mutations.ts", import.meta.url).href);
const { setBaseUrl } = await import(new URL("./endpoints.ts", import.meta.url).href);

function installFetchStub(
  implementation: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = implementation;
  return () => {
    globalThis.fetch = originalFetch;
  };
}

test("refreshDatabase keeps the failed status payload from FastAPI error responses", async () => {
  setBaseUrl("https://api.example.test");
  const restoreFetch = installFetchStub(async (input, init) => {
    assert.equal(String(input), "https://api.example.test/databases/refresh");
    assert.equal(init?.method, "POST");
    assert.deepEqual(JSON.parse(String(init?.body)), {
      force: true,
      trigger: "manual",
      staleAfterSeconds: 120,
    });

    return new Response(
      JSON.stringify({
        status: "failed",
        trigger: "manual",
        startedAt: "2026-03-18T10:00:00Z",
        finishedAt: "2026-03-18T10:00:02Z",
        durationMs: 2000,
        error: "refresh exploded",
        lastSuccessfulRefreshAt: "2026-03-18T09:00:00Z",
        idempotencyKey: "refresh-123",
        scopeLabel: "Historical conversations",
        windowDays: 30,
        windowStart: "2026-02-17T00:00:00Z",
        windowEnd: "2026-03-18T00:00:00Z",
        sourceConversationCount: 42,
        refreshIntervalMinutes: 360,
        runtime: {
          analyticsReadBackend: "legacy",
          conversationSummaryReadBackend: "legacy",
        },
        databases: {
          frontendCache: {
            key: "frontend_cache",
            label: "Frontend Short-Term Cache",
            engine: "In-process memory",
            role: "cache",
            availability: "ready",
            tableCount: 0,
            load: [],
            tables: [],
          },
          sqlite: {
            key: "sqlite",
            label: "SQLite Metadata Store",
            engine: "SQLite",
            role: "metadata",
            availability: "ready",
            tableCount: 2,
            load: [],
            tables: [],
          },
          prefectPostgres: {
            key: "prefect_postgres",
            label: "Prefect Postgres",
            engine: "Postgres",
            role: "orchestration",
            availability: "ready",
            tableCount: 0,
            load: [],
            tables: [],
          },
        },
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  });

  try {
    const status = await refreshDatabase({
      force: true,
      trigger: "manual",
      staleAfterSeconds: 120,
    });
    assert.equal(status.status, "failed");
    assert.equal(status.error, "refresh exploded");
    assert.equal(status.databases.frontendCache.key, "frontend_cache");
    assert.equal(status.databases.prefectPostgres.key, "prefect_postgres");
  } finally {
    restoreFetch();
  }
});

test("createEvaluationPrompt posts to the FastAPI endpoint and normalizes the response", async () => {
  setBaseUrl("https://api.example.test");
  const restoreFetch = installFetchStub(async (input, init) => {
    assert.equal(String(input), "https://api.example.test/evaluation-prompts");
    assert.equal(init?.method, "POST");
    assert.deepEqual(JSON.parse(String(init?.body)), {
      name: "Reviewer Sweep",
      description: "Focus on failures",
      promptText: "Review the weakest turns.",
    });

    return new Response(
      JSON.stringify({
        prompt_id: "prompt-1",
        name: "Reviewer Sweep",
        description: "Focus on failures",
        prompt_text: "Review the weakest turns.",
        is_default: false,
        created_at: "2026-03-18T10:00:00Z",
        updated_at: "2026-03-18T10:00:00Z",
      }),
      {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }
    );
  });

  try {
    const prompt = await createEvaluationPrompt({
      name: "Reviewer Sweep",
      description: "Focus on failures",
      promptText: "Review the weakest turns.",
    });
    assert.equal(prompt.promptId, "prompt-1");
    assert.equal(prompt.promptText, "Review the weakest turns.");
  } finally {
    restoreFetch();
  }
});

test("createEvaluationPrompt validates outgoing payloads before fetch", async () => {
  setBaseUrl("https://api.example.test");
  let fetchCalls = 0;
  const restoreFetch = installFetchStub(async () => {
    fetchCalls += 1;
    throw new Error("fetch should not run");
  });

  try {
    await assert.rejects(
      () =>
        createEvaluationPrompt({
          name: "   ",
          description: "Focus on failures",
          promptText: "Review the weakest turns.",
        }),
      /name/i
    );
    assert.equal(fetchCalls, 0);
  } finally {
    restoreFetch();
  }
});

test("saveSubscriptionSettings and createConversationEvaluation normalize FastAPI payloads", async () => {
  setBaseUrl("https://api.example.test");
  const responses = [
    new Response(
      JSON.stringify({
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
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    ),
    new Response(
      JSON.stringify({
        evaluation_id: "evaluation-1",
        conversation_id: "claude:session-1",
        prompt_id: "prompt-1",
        provider: "codex",
        model: "gpt-5",
        status: "running",
        scope: "full",
        selection_instruction: null,
        prompt_name: "Reviewer Sweep",
        prompt_text: "Review the weakest turns.",
        report_markdown: null,
        raw_output: null,
        error_message: null,
        command: "codex exec --model gpt-5",
        created_at: "2026-03-18T10:00:00Z",
        finished_at: null,
        duration_ms: null,
      }),
      {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }
    ),
  ];
  const seenRequests: Array<{ url: string; method: string | undefined }> = [];
  const restoreFetch = installFetchStub(async (input, init) => {
    seenRequests.push({ url: String(input), method: init?.method });
    const next = responses.shift();
    if (!next) {
      throw new Error("No response stub left.");
    }
    return next;
  });

  try {
    const settings = await saveSubscriptionSettings({
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
    const evaluation = await createConversationEvaluation(
      "-Users-tony-Code-helaicopter",
      "session-1",
      {
        provider: "codex",
        model: "gpt-5",
        promptId: "prompt-1",
        promptName: "Reviewer Sweep",
        promptText: "Review the weakest turns.",
        scope: "full",
        selectionInstruction: null,
      }
    );

    assert.equal(settings.claude.hasSubscription, false);
    assert.equal(settings.claude.monthlyCost, 123.45);
    assert.equal(evaluation.evaluationId, "evaluation-1");
    assert.equal(evaluation.promptName, "Reviewer Sweep");
    assert.deepEqual(seenRequests, [
      {
        url: "https://api.example.test/subscription-settings",
        method: "PATCH",
      },
      {
        url: "https://api.example.test/conversations/-Users-tony-Code-helaicopter/session-1/evaluations",
        method: "POST",
      },
    ]);
  } finally {
    restoreFetch();
  }
});

test("createConversationEvaluation validates outgoing payloads before fetch", async () => {
  setBaseUrl("https://api.example.test");
  let fetchCalls = 0;
  const restoreFetch = installFetchStub(async () => {
    fetchCalls += 1;
    throw new Error("fetch should not run");
  });

  try {
    await assert.rejects(
      () =>
        createConversationEvaluation("-Users-tony-Code-helaicopter", "session-1", {
          provider: "codex",
          model: "gpt-5",
          promptId: "prompt-1",
          promptName: "Reviewer Sweep",
          promptText: "Review the weakest turns.",
          scope: "invalid-scope" as never,
          selectionInstruction: null,
        }),
      /scope/i
    );
    assert.equal(fetchCalls, 0);
  } finally {
    restoreFetch();
  }
});

test("saveSubscriptionSettings validates outgoing payloads before fetch", async () => {
  setBaseUrl("https://api.example.test");
  let fetchCalls = 0;
  const restoreFetch = installFetchStub(async () => {
    fetchCalls += 1;
    throw new Error("fetch should not run");
  });

  try {
    await assert.rejects(
      () =>
        saveSubscriptionSettings({
          claude: {
            provider: "claude",
            hasSubscription: false,
            monthlyCost: Number.NaN,
            updatedAt: "2026-03-18T10:00:00Z",
          },
          codex: {
            provider: "codex",
            hasSubscription: true,
            monthlyCost: 200,
            updatedAt: "2026-03-18T10:00:00Z",
          },
        }),
      /monthlyCost|monthly_cost/i
    );
    assert.equal(fetchCalls, 0);
  } finally {
    restoreFetch();
  }
});
