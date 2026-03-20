import test from "node:test";
import assert from "node:assert/strict";

import type { OvernightOatsRunRecord } from "@/lib/types";
import { buildOatsViewModel } from "./oats-view-model";

function buildRunFixture(): OvernightOatsRunRecord {
  return {
    source: "overnight-oats",
    contractVersion: "oats-runtime-v2",
    runId: "run-1",
    runTitle: "Stacked PR rollout",
    repoRoot: "/Users/tony/Code/helaicopter",
    configPath: "/Users/tony/Code/helaicopter/.oats/config.toml",
    runSpecPath: "/Users/tony/Code/helaicopter/.oats/runs/run-1/spec.md",
    mode: "full-program",
    integrationBranch: "oats/overnight/runtime-facts",
    taskPrTarget: "oats/overnight/runtime-facts",
    finalPrTarget: "main",
    status: "running",
    stackStatus: "awaiting_task_merge",
    featureBranch: {
      name: "oats/overnight/runtime-facts",
      baseBranch: "main",
    },
    activeTaskId: "task-ui",
    heartbeatAt: "2026-03-20T09:15:00Z",
    finishedAt: null,
    planner: null,
    tasks: [
      {
        taskId: "task-api",
        title: "Implement route",
        dependsOn: [],
        parentBranch: "oats/overnight/runtime-facts",
        status: "succeeded",
        attempts: 1,
        taskPr: {
          number: 11,
          state: "merged",
          mergeGateStatus: "merged",
          baseBranch: "oats/overnight/runtime-facts",
          headBranch: "oats/task/task-api",
          checksSummary: { total: 4, passing: 4 },
          reviewSummary: {
            blockingState: "clear",
            approvals: 1,
            changesRequested: 0,
          },
          isStale: false,
        },
        operationHistory: [],
        invocation: null,
      },
      {
        taskId: "task-ui",
        title: "Patch UI",
        dependsOn: ["task-api"],
        parentBranch: "oats/task/task-api",
        status: "blocked",
        attempts: 1,
        taskPr: {
          number: 12,
          state: "open",
          mergeGateStatus: "awaiting_checks",
          baseBranch: "oats/task/task-api",
          headBranch: "oats/task/task-ui",
          checksSummary: { total: 2, passing: 1, failing: 1 },
          reviewSummary: {
            blockingState: "commented",
            approvals: 0,
            changesRequested: 0,
          },
          isStale: true,
        },
        operationHistory: [
          {
            kind: "conflict_resolution",
            status: "started",
            sessionId: "resolver-session",
            startedAt: "2026-03-20T09:10:00Z",
            finishedAt: null,
            details: { attempt: 1 },
          },
        ],
        invocation: null,
      },
      {
        taskId: "task-docs",
        title: "Document rollout",
        dependsOn: ["task-api", "task-ui"],
        parentBranch: "oats/overnight/runtime-facts",
        status: "pending",
        attempts: 0,
        taskPr: {
          state: "open",
          mergeGateStatus: "merge_ready",
          baseBranch: "oats/overnight/runtime-facts",
          headBranch: "oats/task/task-docs",
          checksSummary: { total: 1, passing: 1 },
          reviewSummary: {
            blockingState: "clear",
            approvals: 1,
            changesRequested: 0,
          },
          isStale: false,
        },
        operationHistory: [],
        invocation: null,
      },
    ],
    createdAt: "2026-03-20T08:45:00Z",
    lastUpdatedAt: "2026-03-20T09:15:00Z",
    isRunning: true,
    recordedAt: "2026-03-20T09:15:00Z",
    recordPath: "/Users/tony/Code/helaicopter/.oats/runs/run-1.json",
    dag: {
      nodes: [],
      edges: [],
      stats: {
        totalNodes: 0,
        totalEdges: 0,
        maxDepth: 0,
        maxBreadth: 0,
        rootCount: 0,
        providerBreakdown: {},
        timedOutCount: 0,
        activeCount: 0,
        pendingCount: 0,
        failedCount: 0,
        succeededCount: 0,
      },
    },
    finalPr: {
      number: 42,
      state: "open",
      reviewGateStatus: "awaiting_human",
      baseBranch: "main",
      headBranch: "oats/overnight/runtime-facts",
      checksSummary: { total: 5, passing: 5 },
      isStale: false,
    },
    operationHistory: [
      {
        kind: "refresh",
        status: "succeeded",
        sessionId: "refresh-session",
        startedAt: "2026-03-20T09:14:00Z",
        finishedAt: "2026-03-20T09:14:30Z",
        details: { refreshed: 3 },
      },
    ],
  };
}

test("buildOatsViewModel aligns selected task across the DAG and PR stack", () => {
  const viewModel = buildOatsViewModel(buildRunFixture(), "task-ui");

  assert.equal(viewModel.selectedTask?.taskId, "task-ui");
  assert.equal(viewModel.selectedNodeId, "task-ui");
  assert.deepEqual(
    viewModel.stackItems.map((item) => ({
      taskId: item.taskId,
      depth: item.depth,
      selected: item.isSelected,
    })),
    [
      { taskId: "task-api", depth: 0, selected: false },
      { taskId: "task-ui", depth: 1, selected: true },
      { taskId: "task-docs", depth: 0, selected: false },
    ]
  );
  assert.equal(viewModel.taskPrSummary.total, 3);
  assert.equal(viewModel.taskPrSummary.merged, 1);
  assert.equal(viewModel.taskPrSummary.awaitingChecks, 1);
  assert.equal(viewModel.taskPrSummary.mergeReady, 1);
  assert.equal(viewModel.selectedOperationHistory[0].sessionId, "resolver-session");
});

test("buildOatsViewModel falls back to the active task when the requested task is missing", () => {
  const viewModel = buildOatsViewModel(buildRunFixture(), "missing-task");

  assert.equal(viewModel.selectedTask?.taskId, "task-ui");
  assert.equal(viewModel.selectedNodeId, "task-ui");
  assert.equal(viewModel.selectedOperationHistory[0].kind, "conflict_resolution");
});
