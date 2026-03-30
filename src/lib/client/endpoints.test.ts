import test from "node:test";
import assert from "node:assert/strict";

async function loadEndpoints(nextPublicApiBaseUrl?: string) {
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

test("endpoint builders fall back to the backend proxy prefix when NEXT_PUBLIC_API_BASE_URL is unset", async () => {
  const endpoints = await loadEndpoints();

  assert.equal(endpoints.projects(), "/api/backend/projects");
  assert.equal(endpoints.plans(), "/api/backend/plans");
  assert.equal(
    endpoints.conversation("-Users-tony-Code-helaicopter", "session-123"),
    "/api/backend/conversations/-Users-tony-Code-helaicopter/session-123"
  );
});
