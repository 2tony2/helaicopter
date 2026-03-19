import test from "node:test";
import assert from "node:assert/strict";

import {
  buildConversationRoute,
  buildConversationSubagentRoute,
  buildOrchestrationRoute,
  getConversationRouteState,
  getOrchestrationRouteState,
  normalizePrefectUiPath,
  resolveConversationDetailTab,
} from "./routes";

test("conversation routes preserve deep-link state for tabs and selected entities", () => {
  assert.equal(
    buildConversationRoute("-Users-tony-Code-helaicopter", "session-1", {
      tab: "subagents",
      subagent: "agent-1",
    }),
    "/conversations/-Users-tony-Code-helaicopter/session-1?tab=subagents&subagent=agent-1"
  );
  assert.equal(
    buildConversationSubagentRoute(
      "-Users-tony-Code-helaicopter",
      "session-1",
      "agent-1"
    ),
    "/conversations/-Users-tony-Code-helaicopter/session-1/subagents/agent-1"
  );
  assert.equal(resolveConversationDetailTab("dag"), "dag");
  assert.equal(resolveConversationDetailTab("unknown"), "messages");
});

test("orchestration routes preserve Prefect iframe state", () => {
  assert.equal(
    buildOrchestrationRoute({
      tab: "prefect-ui",
      flowRunId: "flow-run-1",
      prefectPath: "flow-runs/flow-run/flow-run-1",
    }),
    "/orchestration?tab=prefect-ui&flowRunId=flow-run-1&prefectPath=%2Fflow-runs%2Fflow-run%2Fflow-run-1"
  );
  assert.equal(normalizePrefectUiPath("flow-runs"), "/flow-runs");
  assert.equal(normalizePrefectUiPath(""), undefined);
});

test("conversation route state prefers current query params over stale initial props", () => {
  const state = getConversationRouteState(
    new URLSearchParams("tab=subagents&subagent=agent-2"),
    {
      tab: "messages",
      plan: "plan-1",
      subagent: "agent-1",
    }
  );

  assert.deepEqual(state, {
    tab: "subagents",
    plan: "plan-1",
    subagent: "agent-2",
  });
});

test("orchestration route state prefers current query params over stale initial props", () => {
  const state = getOrchestrationRouteState(
    new URLSearchParams("tab=prefect-ui&flowRunId=flow-run-2&prefectPath=/flow-runs/flow-run/flow-run-2"),
    {
      tab: "prefect",
      flowRunId: "flow-run-1",
      prefectPath: "/flow-runs",
    }
  );

  assert.deepEqual(state, {
    tab: "prefect-ui",
    flowRunId: "flow-run-2",
    prefectPath: "/flow-runs/flow-run/flow-run-2",
  });
});
