import test from "node:test";
import assert from "node:assert/strict";

import {
  buildPrefectUiUrl,
  PREFECT_UI_URL,
  resolveOrchestrationInitialTab,
} from "./tabs";

test("resolveOrchestrationInitialTab defaults to prefect and accepts prefect-ui", () => {
  assert.equal(resolveOrchestrationInitialTab(undefined), "prefect");
  assert.equal(resolveOrchestrationInitialTab("prefect"), "prefect");
  assert.equal(resolveOrchestrationInitialTab("prefect-ui"), "prefect-ui");
  assert.equal(
    resolveOrchestrationInitialTab("conversation-dags"),
    "conversation-dags"
  );
  assert.equal(resolveOrchestrationInitialTab("unknown"), "prefect");
});

test("PREFECT_UI_URL points at the local self-hosted Prefect UI", () => {
  assert.equal(PREFECT_UI_URL, "http://127.0.0.1:4200");
  assert.equal(buildPrefectUiUrl("/flow-runs/flow-run/flow-run-1"), `${PREFECT_UI_URL}/flow-runs/flow-run/flow-run-1`);
});
