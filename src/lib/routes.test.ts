import test from "node:test";
import assert from "node:assert/strict";

import {
  buildConversationBaseRoute,
  buildConversationMessageRoute,
  buildConversationPlanRoute,
  buildConversationRoute,
  buildConversationSubagentTabRoute,
  buildConversationTabRoute,
  buildOrchestrationRoute,
  decideConversationRoute,
  getOrchestrationRouteState,
  normalizePrefectUiPath,
  parseConversationRouteSegments,
  translateLegacyConversationRouteTarget,
} from "./routes";

const conversationRef = "review-the-backend-rollout--claude-claude-session-1";
const wrongSlugConversationRef = "stale-route-slug--claude-claude-session-1";

test("canonical conversation route builders produce tab and nested segment paths", () => {
  assert.equal(
    buildConversationBaseRoute(conversationRef),
    "/conversations/review-the-backend-rollout--claude-claude-session-1"
  );
  assert.equal(
    buildConversationTabRoute(conversationRef, "plans"),
    "/conversations/review-the-backend-rollout--claude-claude-session-1/plans"
  );
  assert.equal(
    buildConversationMessageRoute(conversationRef, "assistant-uuid-1"),
    "/conversations/review-the-backend-rollout--claude-claude-session-1/messages/assistant-uuid-1"
  );
  assert.equal(
    buildConversationPlanRoute(conversationRef, "plan-7"),
    "/conversations/review-the-backend-rollout--claude-claude-session-1/plans/plan-7"
  );
  assert.equal(
    buildConversationSubagentTabRoute(conversationRef, "agent-1"),
    "/conversations/review-the-backend-rollout--claude-claude-session-1/subagents/agent-1"
  );
});

test("legacy query-param builder drops stale entity params when switching tabs", () => {
  assert.equal(
    buildConversationRoute("-Users-tony-Code-helaicopter", "claude-session-1", {
      tab: "plans",
      message: "assistant-uuid-1",
    }),
    "/conversations/-Users-tony-Code-helaicopter/claude-session-1?tab=plans"
  );
  assert.equal(
    buildConversationRoute("-Users-tony-Code-helaicopter", "claude-session-1", {
      tab: "messages",
      plan: "plan-7",
    }),
    "/conversations/-Users-tony-Code-helaicopter/claude-session-1"
  );
  assert.equal(
    buildConversationRoute("-Users-tony-Code-helaicopter", "claude-session-1", {
      tab: "subagents",
      plan: "plan-7",
      subagent: "agent-1",
    }),
    "/conversations/-Users-tony-Code-helaicopter/claude-session-1?tab=subagents&subagent=agent-1"
  );
});

test("canonical catch-all parsing accepts valid tab and nested segment shapes", () => {
  assert.deepEqual(parseConversationRouteSegments([conversationRef]), {
    kind: "canonical",
    conversationRef,
    routeSlug: "review-the-backend-rollout",
    provider: "claude",
    sessionId: "claude-session-1",
    tab: "messages",
    isBaseRoute: true,
  });
  assert.deepEqual(parseConversationRouteSegments([conversationRef, "dag"]), {
    kind: "canonical",
    conversationRef,
    routeSlug: "review-the-backend-rollout",
    provider: "claude",
    sessionId: "claude-session-1",
    tab: "dag",
    isBaseRoute: false,
  });
  assert.deepEqual(
    parseConversationRouteSegments([conversationRef, "messages", "assistant-uuid-1"]),
    {
      kind: "canonical",
      conversationRef,
      routeSlug: "review-the-backend-rollout",
      provider: "claude",
      sessionId: "claude-session-1",
      tab: "messages",
      isBaseRoute: false,
      messageId: "assistant-uuid-1",
    }
  );
  assert.deepEqual(
    parseConversationRouteSegments([conversationRef, "plans", "plan-7"]),
    {
      kind: "canonical",
      conversationRef,
      routeSlug: "review-the-backend-rollout",
      provider: "claude",
      sessionId: "claude-session-1",
      tab: "plans",
      isBaseRoute: false,
      planId: "plan-7",
    }
  );
  assert.deepEqual(
    parseConversationRouteSegments([conversationRef, "subagents", "agent-1"]),
    {
      kind: "canonical",
      conversationRef,
      routeSlug: "review-the-backend-rollout",
      provider: "claude",
      sessionId: "claude-session-1",
      tab: "subagents",
      isBaseRoute: false,
      agentId: "agent-1",
    }
  );
});

test("catch-all parsing distinguishes legacy routes and rejects invalid canonical shapes", () => {
  assert.deepEqual(
    parseConversationRouteSegments(["-Users-tony-Code-helaicopter", "claude-session-1"]),
    {
      kind: "legacy",
      projectPath: "-Users-tony-Code-helaicopter",
      sessionId: "claude-session-1",
    }
  );
  assert.deepEqual(
    parseConversationRouteSegments([
      "-Users-tony-Code-helaicopter",
      "claude-session-1",
      "subagents",
      "agent-1",
    ]),
    {
      kind: "legacy",
      projectPath: "-Users-tony-Code-helaicopter",
      sessionId: "claude-session-1",
      agentId: "agent-1",
    }
  );
  assert.deepEqual(
    parseConversationRouteSegments(["foo--claude-bar", "session-1"]),
    {
      kind: "legacy",
      projectPath: "foo--claude-bar",
      sessionId: "session-1",
    }
  );
  assert.deepEqual(
    parseConversationRouteSegments(["foo--claude-bar", "session-1", "subagents", "agent-1"]),
    {
      kind: "legacy",
      projectPath: "foo--claude-bar",
      sessionId: "session-1",
      agentId: "agent-1",
    }
  );
  assert.deepEqual(parseConversationRouteSegments([conversationRef, "unknown"]), {
    kind: "invalid",
  });
  assert.deepEqual(parseConversationRouteSegments([conversationRef, "unknown", "extra"]), {
    kind: "invalid",
  });
  assert.deepEqual(parseConversationRouteSegments([conversationRef, "failed", "extra"]), {
    kind: "invalid",
  });
});

test("legacy query params translate into canonical targets with deterministic precedence", () => {
  assert.deepEqual(translateLegacyConversationRouteTarget(new URLSearchParams()), {
    tab: "messages",
  });
  assert.deepEqual(
    translateLegacyConversationRouteTarget(
      new URLSearchParams("tab=messages&message=assistant-uuid-1")
    ),
    {
      tab: "messages",
      messageId: "assistant-uuid-1",
    }
  );
  assert.deepEqual(
    translateLegacyConversationRouteTarget(new URLSearchParams("plan=plan-7")),
    {
      tab: "plans",
      planId: "plan-7",
    }
  );
  assert.deepEqual(
    translateLegacyConversationRouteTarget(
      new URLSearchParams("tab=plans&message=assistant-uuid-1&plan=plan-7&subagent=agent-1")
    ),
    {
      tab: "plans",
      planId: "plan-7",
    }
  );
  assert.deepEqual(
    translateLegacyConversationRouteTarget(
      new URLSearchParams("tab=failed&message=assistant-uuid-1&plan=plan-7&subagent=agent-1")
    ),
    {
      tab: "messages",
      messageId: "assistant-uuid-1",
    }
  );
  assert.deepEqual(
    translateLegacyConversationRouteTarget(new URLSearchParams("tab=unknown")),
    {
      tab: "messages",
    }
  );
});

test("route decisions redirect canonical base paths and legacy routes to canonical targets", () => {
  assert.deepEqual(
    decideConversationRoute(parseConversationRouteSegments([conversationRef]), {
      resolution: { conversationRef },
    }),
    {
      kind: "redirect",
      href: "/conversations/review-the-backend-rollout--claude-claude-session-1/messages",
    }
  );

  assert.deepEqual(
    decideConversationRoute(
      parseConversationRouteSegments(["-Users-tony-Code-helaicopter", "claude-session-1"]),
      {
        resolution: { conversationRef },
        searchParams: new URLSearchParams("tab=plans&plan=plan-7"),
      }
    ),
    {
      kind: "redirect",
      href: "/conversations/review-the-backend-rollout--claude-claude-session-1/plans/plan-7",
    }
  );

  assert.deepEqual(
    decideConversationRoute(
      parseConversationRouteSegments([
        "-Users-tony-Code-helaicopter",
        "claude-session-1",
        "subagents",
        "agent-1",
      ]),
      {
        resolution: { conversationRef },
      }
    ),
    {
      kind: "redirect",
      href: "/conversations/review-the-backend-rollout--claude-claude-session-1/subagents/agent-1",
    }
  );
});

test("route decisions redirect wrong-slug canonical paths to the resolver's canonical ref", () => {
  assert.deepEqual(
    decideConversationRoute(
      parseConversationRouteSegments([
        wrongSlugConversationRef,
        "messages",
        "assistant-uuid-1",
      ]),
      {
        resolution: { conversationRef },
        validMessageIds: ["assistant-uuid-1"],
      }
    ),
    {
      kind: "redirect",
      href: "/conversations/review-the-backend-rollout--claude-claude-session-1/messages/assistant-uuid-1",
    }
  );
});

test("route decisions render valid canonical nested routes and 404 invalid canonical targets", () => {
  assert.deepEqual(
    decideConversationRoute(
      parseConversationRouteSegments([conversationRef, "plans", "plan-7"]),
      {
        resolution: { conversationRef },
        validPlanIds: ["plan-7"],
      }
    ),
    {
      kind: "render",
      conversationRef,
      tab: "plans",
      planId: "plan-7",
    }
  );

  assert.deepEqual(
    decideConversationRoute(
      parseConversationRouteSegments([conversationRef, "messages", "missing-message"]),
      {
        resolution: { conversationRef },
        validMessageIds: ["assistant-uuid-1"],
      }
    ),
    {
      kind: "not-found",
    }
  );
  assert.deepEqual(
    decideConversationRoute(
      parseConversationRouteSegments([conversationRef, "plans", "missing-plan"]),
      {
        resolution: { conversationRef },
        validPlanIds: ["plan-7"],
      }
    ),
    {
      kind: "not-found",
    }
  );
  assert.deepEqual(
    decideConversationRoute(
      parseConversationRouteSegments([conversationRef, "subagents", "missing-agent"]),
      {
        resolution: { conversationRef },
        validAgentIds: ["agent-1"],
      }
    ),
    {
      kind: "not-found",
    }
  );
  assert.deepEqual(
    decideConversationRoute(parseConversationRouteSegments([conversationRef, "unknown"]), {
      resolution: { conversationRef },
    }),
    {
      kind: "not-found",
    }
  );
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
  assert.equal(buildOrchestrationRoute(), "/orchestration");
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
