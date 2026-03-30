import test from "node:test";
import assert from "node:assert/strict";

import { getAppDocsNavigation, loadAppDoc } from "./docs";

test("loadAppDoc resolves the docs landing page from repo docs", () => {
  const page = loadAppDoc();
  assert.ok(page);
  assert.equal(page?.href, "/docs");
  assert.equal(page?.title, "Helaicopter Platform Documentation");
});

test("loadAppDoc resolves nested documentation pages", () => {
  const page = loadAppDoc(["api", "overview"]);
  assert.ok(page);
  assert.equal(page?.href, "/docs/api/overview");
  assert.match(page?.body ?? "", /OpenAPI|API/i);
});

test("getAppDocsNavigation returns repo-backed entries with docs routes", () => {
  const entries = getAppDocsNavigation();
  assert.ok(entries.some((entry) => entry.href === "/docs/api/overview"));
  assert.ok(!entries.some((entry) => entry.href === "/docs/orchestration/overview"));
});
