import assert from "node:assert/strict";
import test from "node:test";
import { z } from "zod";

async function getFetcher() {
  return import(new URL("./fetcher.ts", import.meta.url).href);
}

function installFetchStub(
  implementation: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = implementation;
  return () => {
    globalThis.fetch = originalFetch;
  };
}

test("requestJson parses successful JSON responses through a schema", async () => {
  const payloadSchema = z.object({
    projectId: z.string(),
    count: z.number(),
  });
  const restoreFetch = installFetchStub(async (input, init) => {
    assert.equal(String(input), "https://api.example.test/projects/alpha");
    assert.equal(init?.method, "GET");

    return new Response(JSON.stringify({ projectId: "alpha", count: 3 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    const { requestJson } = await getFetcher();
    const payload = await requestJson("https://api.example.test/projects/alpha", { method: "GET" }, payloadSchema);

    assert.equal(payload.projectId, "alpha");
    assert.equal(payload.count, 3);
  } finally {
    restoreFetch();
  }
});

test("requestJson disables browser caching by default for repeated live reads", async () => {
  const payloadSchema = z.object({
    ok: z.boolean(),
  });
  const restoreFetch = installFetchStub(async (input, init) => {
    assert.equal(String(input), "https://api.example.test/conversations?days=7");
    assert.equal(init?.cache, "no-store");

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    const { requestJson } = await getFetcher();
    const payload = await requestJson(
      "https://api.example.test/conversations?days=7",
      undefined,
      payloadSchema
    );

    assert.equal(payload.ok, true);
  } finally {
    restoreFetch();
  }
});

test("requestJson throws a concise validation error when schema parsing fails", async () => {
  const payloadSchema = z.object({
    projectId: z.string(),
    count: z.number(),
  });
  const restoreFetch = installFetchStub(async () => {
    return new Response(JSON.stringify({ projectId: "alpha", count: "3" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    const { requestJson } = await getFetcher();
    await assert.rejects(
      () => requestJson("https://api.example.test/projects/alpha", undefined, payloadSchema),
      (error: unknown) => {
        assert.ok(error instanceof Error);
        assert.match(error.message, /response validation failed/i);
        assert.match(error.message, /count/i);
        assert.match(error.message, /number/i);
        return true;
      }
    );
  } finally {
    restoreFetch();
  }
});

test("requestJson prefers backend error messages for non-OK responses even with a schema", async () => {
  const payloadSchema = z.object({
    projectId: z.string(),
  });
  const restoreFetch = installFetchStub(async () => {
    return new Response(JSON.stringify({ error: "Project lookup exploded." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    const { requestJson } = await getFetcher();
    await assert.rejects(
      () => requestJson("https://api.example.test/projects/alpha", undefined, payloadSchema),
      /Project lookup exploded\./
    );
  } finally {
    restoreFetch();
  }
});

test("requestJson keeps legacy normalize-only call sites working during migration", async () => {
  const restoreFetch = installFetchStub(async () => {
    return new Response(JSON.stringify({ project_id: "alpha" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    const { requestJson } = await getFetcher();
    const payload = await requestJson(
      "https://api.example.test/projects/alpha",
      undefined,
      (value: unknown) => {
        assert.deepEqual(value, { project_id: "alpha" });
        return { projectId: (value as { project_id: string }).project_id };
      }
    );

    assert.deepEqual(payload, { projectId: "alpha" });
  } finally {
    restoreFetch();
  }
});

test("requestJson validates with a schema before running a follow-up normalizer", async () => {
  const payloadSchema = z.object({
    projectId: z.string(),
    count: z.number().int().nonnegative(),
  });
  const restoreFetch = installFetchStub(async () => {
    return new Response(JSON.stringify({ projectId: "alpha", count: 3 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    const { requestJson } = await getFetcher();
    const payload = await requestJson(
      "https://api.example.test/projects/alpha",
      undefined,
      payloadSchema,
      (value: { projectId: string; count: number }) => {
        assert.deepEqual(value, { projectId: "alpha", count: 3 });
        return `${value.projectId}:${value.count}`;
      }
    );

    assert.equal(payload, "alpha:3");
  } finally {
    restoreFetch();
  }
});

test("mutation helpers carry schema-aware parsing through post, patch, and delete", async () => {
  const payloadSchema = z.object({
    projectId: z.string(),
    count: z.number().int(),
  });
  const seenRequests: Array<{ url: string; method: string | undefined; body: string | undefined }> = [];
  const responses = [
    new Response(JSON.stringify({ projectId: "alpha", count: 3 }), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    }),
    new Response(JSON.stringify({ projectId: "beta", count: 4 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
    new Response(JSON.stringify({ projectId: "gamma", count: 5 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  ];
  const restoreFetch = installFetchStub(async (input, init) => {
    seenRequests.push({
      url: String(input),
      method: init?.method,
      body: typeof init?.body === "string" ? init.body : undefined,
    });
    const response = responses.shift();
    if (!response) {
      throw new Error("No response stub left.");
    }
    return response;
  });

  try {
    const { post, patch, del } = await getFetcher();
    const created = await post(
      "https://api.example.test/projects",
      { projectId: "alpha" },
      payloadSchema,
      (value: { projectId: string; count: number }) => `${value.projectId}:${value.count}`
    );
    const updated = await patch(
      "https://api.example.test/projects/beta",
      { archived: false },
      payloadSchema,
      (value: { projectId: string; count: number }) => value.count
    );
    const removed = await del(
      "https://api.example.test/projects/gamma",
      payloadSchema,
      (value: { projectId: string; count: number }) => value.projectId
    );

    assert.equal(created, "alpha:3");
    assert.equal(updated, 4);
    assert.equal(removed, "gamma");
    assert.deepEqual(seenRequests, [
      {
        url: "https://api.example.test/projects",
        method: "POST",
        body: JSON.stringify({ projectId: "alpha" }),
      },
      {
        url: "https://api.example.test/projects/beta",
        method: "PATCH",
        body: JSON.stringify({ archived: false }),
      },
      {
        url: "https://api.example.test/projects/gamma",
        method: "DELETE",
        body: undefined,
      },
    ]);
  } finally {
    restoreFetch();
  }
});

test("requestJson bounds validation errors, strips raw query strings, and skips the normalizer on schema failures", async () => {
  let normalizeCalls = 0;
  const payloadSchema = z.object({
    projectId: z.string(),
    count: z.number(),
    state: z.enum(["ready"]),
    owner: z.string(),
    region: z.string(),
  });
  const restoreFetch = installFetchStub(async () => {
    return new Response(
      JSON.stringify({
        projectId: 42,
        count: "3",
        state: "broken",
        owner: 9,
        region: false,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  });

  try {
    const { requestJson } = await getFetcher();
    await assert.rejects(
      () =>
        requestJson(
          "https://api.example.test/projects/alpha?token=super-secret&trace=abc123",
          undefined,
          payloadSchema,
          (value: unknown) => {
            normalizeCalls += 1;
            return value;
          }
        ),
      (error: unknown) => {
        assert.ok(error instanceof Error);
        assert.match(error.message, /response validation failed for https:\/\/api\.example\.test\/projects\/alpha/i);
        assert.doesNotMatch(error.message, /token=super-secret/);
        assert.doesNotMatch(error.message, /trace=abc123/);
        assert.match(error.message, /projectId/i);
        assert.match(error.message, /count/i);
        assert.match(error.message, /\d+ more/i);
        return true;
      }
    );

    assert.equal(normalizeCalls, 0);
  } finally {
    restoreFetch();
  }
});
