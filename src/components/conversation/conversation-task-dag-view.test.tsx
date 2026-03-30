import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ConversationTaskDagView } from "./conversation-task-dag-view.tsx";

test("ConversationTaskDagView renders task summary content for parsed Codex plans", () => {
  const markup = renderToStaticMarkup(
    <ConversationTaskDagView
      dag={{
        source: "codex-plan",
        stats: {
          totalNodes: 2,
          totalEdges: 1,
          completedNodes: 1,
        },
        nodes: [
          {
            id: "plan-2-step-1",
            taskId: "plan-2-step-1",
            title: "Inspect current task payloads",
            status: "completed",
            dependsOn: [],
            source: "plan",
          },
          {
            id: "plan-2-step-2",
            taskId: "plan-2-step-2",
            title: "Render DAG in Tasks tab",
            status: "in_progress",
            dependsOn: ["plan-2-step-1"],
            source: "plan",
          },
        ],
        edges: [
          {
            id: "plan-2-step-1->plan-2-step-2",
            source: "plan-2-step-1",
            target: "plan-2-step-2",
            inferred: false,
          },
        ],
      }}
    />
  );

  assert.match(markup, /Task DAG/);
  assert.match(markup, /latest Codex plan/);
  assert.match(markup, /Parsed tasks/);
  assert.match(markup, /Inspect current task payloads/);
  assert.match(markup, /Render DAG in Tasks tab/);
});
