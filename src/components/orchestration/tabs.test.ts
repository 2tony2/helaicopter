import test from "node:test";
import assert from "node:assert/strict";

import {
  resolveOrchestrationInitialTab,
} from "./tabs";

test("resolveOrchestrationInitialTab defaults to orchestration and accepts valid tabs", () => {
  assert.equal(resolveOrchestrationInitialTab(undefined), "orchestration");
  assert.equal(resolveOrchestrationInitialTab("orchestration"), "orchestration");
  assert.equal(
    resolveOrchestrationInitialTab("conversation-dags"),
    "conversation-dags"
  );
  assert.equal(resolveOrchestrationInitialTab("unknown"), "orchestration");
});
