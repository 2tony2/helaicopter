import assert from "node:assert/strict";
import test from "node:test";

import { buildConversationTaskDag } from "./conversation-task-dag.ts";

test("buildConversationTaskDag honors explicit dependency fields from task payloads", () => {
  const dag = buildConversationTaskDag({
    provider: "claude",
    tasks: [
      { taskId: "api", title: "API" },
      { taskId: "ui", title: "UI", dependsOn: ["api"] },
      { taskId: "qa", title: "QA", dependencies: [{ taskId: "ui" }] },
    ],
    plans: [],
  });

  assert.equal(dag.source, "tasks");
  assert.deepEqual(
    dag.nodes.map((node) => ({
      taskId: node.taskId,
      dependsOn: node.dependsOn,
    })),
    [
      { taskId: "api", dependsOn: [] },
      { taskId: "ui", dependsOn: ["api"] },
      { taskId: "qa", dependsOn: ["ui"] },
    ]
  );
  assert.deepEqual(
    dag.edges.map((edge) => `${edge.source}->${edge.target}`),
    ["api->ui", "ui->qa"]
  );
});

test("buildConversationTaskDag falls back to a linear ordered chain when tasks have no explicit dependencies", () => {
  const dag = buildConversationTaskDag({
    provider: "claude",
    tasks: [
      { taskId: "t1", title: "Collect context" },
      { taskId: "t2", title: "Patch UI" },
      { taskId: "t3", title: "Verify" },
    ],
    plans: [],
  });

  assert.equal(dag.source, "tasks");
  assert.deepEqual(
    dag.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      inferred: edge.inferred,
    })),
    [
      { source: "t1", target: "t2", inferred: true },
      { source: "t2", target: "t3", inferred: true },
    ]
  );
});

test("buildConversationTaskDag derives Codex task nodes from the latest plan when no task payload exists", () => {
  const dag = buildConversationTaskDag({
    provider: "codex",
    tasks: [],
    plans: [
      {
        id: "plan-1",
        slug: "plan-1",
        title: "Old plan",
        preview: "Preview",
        content: "Content",
        provider: "codex",
        timestamp: 10,
        sessionId: "session-1",
        projectPath: "codex:-Users-tony-Code-helaicopter",
        steps: [{ step: "Old step", status: "pending" }],
      },
      {
        id: "plan-2",
        slug: "plan-2",
        title: "Latest plan",
        preview: "Preview",
        content: "Content",
        provider: "codex",
        timestamp: 20,
        sessionId: "session-1",
        projectPath: "codex:-Users-tony-Code-helaicopter",
        steps: [
          { step: "Inspect current task payloads", status: "completed" },
          { step: "Render DAG in Tasks tab", status: "in_progress" },
          { step: "Verify Codex fallback", status: "pending" },
        ],
      },
    ],
  });

  assert.equal(dag.source, "codex-plan");
  assert.deepEqual(
    dag.nodes.map((node) => ({
      taskId: node.taskId,
      title: node.title,
      status: node.status,
    })),
    [
      {
        taskId: "plan-2-step-1",
        title: "Inspect current task payloads",
        status: "completed",
      },
      {
        taskId: "plan-2-step-2",
        title: "Render DAG in Tasks tab",
        status: "in_progress",
      },
      {
        taskId: "plan-2-step-3",
        title: "Verify Codex fallback",
        status: "pending",
      },
    ]
  );
  assert.deepEqual(
    dag.edges.map((edge) => `${edge.source}->${edge.target}`),
    ["plan-2-step-1->plan-2-step-2", "plan-2-step-2->plan-2-step-3"]
  );
});
