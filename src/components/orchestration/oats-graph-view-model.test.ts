import test from "node:test";
import assert from "node:assert/strict";

async function getGraphViewModel() {
  return import(new URL("./oats-graph-view-model.ts", import.meta.url).href);
}

function makeRunWithGraph(overrides: Record<string, unknown> = {}) {
  return {
    source: "overnight-oats" as const,
    contractVersion: "oats-runtime-v2" as const,
    runId: "run_abc",
    runTitle: "Test",
    repoRoot: "/tmp",
    configPath: "/tmp/config.toml",
    runSpecPath: "/tmp/spec.md",
    mode: "writable",
    integrationBranch: "feat/x",
    taskPrTarget: "feat/x",
    finalPrTarget: "main",
    status: "running" as const,
    planner: null,
    tasks: [],
    operationHistory: [],
    createdAt: "2026-03-25T00:00:00Z",
    lastUpdatedAt: "2026-03-25T00:01:00Z",
    isRunning: true,
    recordedAt: "2026-03-25T00:01:00Z",
    recordPath: "/tmp/state.json",
    dag: { nodes: [], edges: [], stats: { totalNodes: 0, totalEdges: 0, maxDepth: 0, maxBreadth: 0, rootCount: 0, providerBreakdown: {}, timedOutCount: 0, activeCount: 0, pendingCount: 0, failedCount: 0, succeededCount: 0 } },
    nodes: [
      { taskId: "auth", kind: "implementation", title: "Auth", status: "succeeded", attemptCount: 1, operationCount: 0, discoveredTaskCount: 0 },
      { taskId: "api", kind: "implementation", title: "API", status: "pending", attemptCount: 0, operationCount: 0, discoveredTaskCount: 0 },
    ],
    edges: [
      { fromTask: "auth", toTask: "api", predicate: "code_ready" as const, satisfied: true },
    ],
    readyQueue: ["api"],
    graphMutationCount: 0,
    interruptionCount: 0,
    ...overrides,
  };
}

test("buildGraphViewModel produces edge color map", async () => {
  const { buildGraphViewModel } = await getGraphViewModel();
  const model = buildGraphViewModel(makeRunWithGraph());
  const edge = model.edges[0];
  assert.ok(edge.color);
  assert.equal(edge.color, "blue"); // code_ready = blue
});

test("buildGraphViewModel highlights ready-queue tasks", async () => {
  const { buildGraphViewModel } = await getGraphViewModel();
  const model = buildGraphViewModel(makeRunWithGraph({
    readyQueue: ["auth", "api"],
  }));
  const readyNodes = model.nodes.filter((n: { isReady: boolean }) => n.isReady);
  assert.equal(readyNodes.length, 2);
});

test("buildGraphViewModel shows attempt count", async () => {
  const { buildGraphViewModel } = await getGraphViewModel();
  const model = buildGraphViewModel(makeRunWithGraph({
    nodes: [
      { taskId: "auth", kind: "implementation", title: "Auth", status: "failed", attemptCount: 3, operationCount: 0, discoveredTaskCount: 0, lastAttemptStatus: "failed" },
    ],
  }));
  const authNode = model.nodes.find((n: { taskId: string }) => n.taskId === "auth");
  assert.equal(authNode.attemptCount, 3);
});

test("buildGraphViewModel exposes canRefresh and canResume", async () => {
  const { buildGraphViewModel } = await getGraphViewModel();

  // Active run: can refresh, not resume (no failures)
  const active = buildGraphViewModel(makeRunWithGraph());
  assert.ok(active.canRefresh);
  assert.ok(!active.canResume);

  // Run with failed tasks: can refresh and resume
  const failed = buildGraphViewModel(makeRunWithGraph({
    nodes: [
      { taskId: "auth", kind: "implementation", title: "Auth", status: "failed", attemptCount: 3, operationCount: 0, discoveredTaskCount: 0 },
    ],
  }));
  assert.ok(failed.canRefresh);
  assert.ok(failed.canResume);

  // Completed run: no refresh, no resume
  const completed = buildGraphViewModel(makeRunWithGraph({
    status: "completed",
    nodes: [
      { taskId: "auth", kind: "implementation", title: "Auth", status: "succeeded", attemptCount: 1, operationCount: 0, discoveredTaskCount: 0 },
    ],
  }));
  assert.ok(!completed.canRefresh);
  assert.ok(!completed.canResume);
});

test("buildGraphViewModel marks discovered tasks", async () => {
  const { buildGraphViewModel } = await getGraphViewModel();
  const model = buildGraphViewModel(makeRunWithGraph({
    nodes: [
      { taskId: "api", kind: "implementation", title: "API", status: "succeeded", attemptCount: 1, operationCount: 0, discoveredTaskCount: 1 },
      { taskId: "task_mw", kind: "implementation", title: "Middleware", status: "pending", attemptCount: 0, operationCount: 0, discoveredTaskCount: 0, discoveredBy: "api" },
    ],
  }));
  const discovered = model.nodes.filter((n: { isDiscovered: boolean }) => n.isDiscovered);
  assert.equal(discovered.length, 1);
  assert.equal(discovered[0].discoveredBy, "api");
});

test("buildGraphViewModel edge style: solid when satisfied, dashed when not", async () => {
  const { buildGraphViewModel } = await getGraphViewModel();
  const model = buildGraphViewModel(makeRunWithGraph({
    edges: [
      { fromTask: "auth", toTask: "api", predicate: "code_ready", satisfied: true },
      { fromTask: "api", toTask: "e2e", predicate: "pr_merged", satisfied: false },
    ],
  }));
  assert.equal(model.edges[0].style, "solid");
  assert.equal(model.edges[1].style, "dashed");
});
