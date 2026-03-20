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
} from "./routes.ts";

test("conversation routes preserve deep-link state for tabs and selected entities", () => {
  assert.equal(
    buildConversationRoute("-Users-tony-Code-helaicopter", "session-1", {
      tab: "subagents",
      subagent: "agent-1",
      message: "message-1",
    }),
    "/conversations/-Users-tony-Code-helaicopter/session-1?tab=subagents&subagent=agent-1&message=message-1"
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
  assert.equal(normalizePrefectUiPath("https://prefect.example.test/flow-runs"), undefined);
  assert.equal(buildOrchestrationRoute(), "/orchestration");
});

test("conversation route state prefers current query params over stale initial props", () => {
  const state = getConversationRouteState(
    new URLSearchParams("tab=subagents&subagent=agent-2"),
    {
      tab: "messages",
      plan: "plan-1",
      subagent: "agent-1",
      message: "message-1",
    }
  );

  assert.deepEqual(state, {
    tab: "subagents",
    plan: "plan-1",
    subagent: "agent-2",
    message: "message-1",
  });
});

test("orchestration route state prefers current query params over stale initial props", () => {
  const state = getOrchestrationRouteState(
    new URLSearchParams("tab=prefect-ui&flowRunId=flow-run-2&prefectPath=/flow-runs/flow-run/flow-run-2"),
    {
      tab: "orchestration",
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

test("unsupported tab values fall back to stable defaults", () => {
  assert.equal(resolveConversationDetailTab("unknown"), "messages");

  assert.deepEqual(
    getConversationRouteState(new URLSearchParams("tab=unknown"), {
      tab: "subagents",
      subagent: "agent-1",
    }),
    {
      tab: "messages",
      plan: undefined,
      subagent: "agent-1",
      message: undefined,
    }
  );

  assert.deepEqual(
    getOrchestrationRouteState(
      new URLSearchParams("tab=unknown&prefectPath=https://prefect.example.test/flow-runs"),
      {
        tab: "prefect-ui",
        flowRunId: "flow-run-1",
        prefectPath: "/flow-runs",
      }
    ),
    {
      tab: "orchestration",
      flowRunId: "flow-run-1",
      prefectPath: undefined,
    }
  );
});

test("conversation route state accepts per-message deep links from query params", () => {
  const state = getConversationRouteState(
    new URLSearchParams("tab=messages&message=assistant-uuid-1"),
  );

  assert.deepEqual(state, {
    tab: "messages",
    plan: undefined,
    subagent: undefined,
    message: "assistant-uuid-1",
  });
});
