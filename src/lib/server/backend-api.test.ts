import test from "node:test";
import assert from "node:assert/strict";

const ORIGINAL_ENV = {
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  HELA_API_PORT: process.env.HELA_API_PORT,
};

async function loadBackendApi() {
  return import(new URL(`./backend-api.ts?ts=${Date.now()}`, import.meta.url).href);
}

function restoreEnv() {
  if (ORIGINAL_ENV.NEXT_PUBLIC_API_BASE_URL === undefined) {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  } else {
    process.env.NEXT_PUBLIC_API_BASE_URL = ORIGINAL_ENV.NEXT_PUBLIC_API_BASE_URL;
  }
  if (ORIGINAL_ENV.HELA_API_PORT === undefined) {
    delete process.env.HELA_API_PORT;
  } else {
    process.env.HELA_API_PORT = ORIGINAL_ENV.HELA_API_PORT;
  }
}

test("fetchBackendJson falls back to the checkout-local FastAPI port for SSR", async () => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  process.env.HELA_API_PORT = "31506";

  const seen: string[] = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    seen.push(String(input));
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;

  try {
    const { fetchBackendJson } = await loadBackendApi();
    const response = await fetchBackendJson<{ ok: boolean }>("/conversations/by-ref/example");
    assert.equal(response.status, 200);
    assert.deepEqual(response.data, { ok: true });
    assert.deepEqual(seen, ["http://127.0.0.1:31506/conversations/by-ref/example"]);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv();
  }
});
