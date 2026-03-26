import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { OperatorBootstrapPanel } from "@/components/orchestration/operator-bootstrap-panel";

test("operator bootstrap panel renders actionable next steps for blocked states", () => {
  const markup = renderToStaticMarkup(
    <OperatorBootstrapPanel
      summary={{
        overallStatus: "blocked",
        resolverRunning: false,
        blockingReasons: [
          {
            code: "resolver_not_running",
            severity: "error",
            message: "The backend resolver loop is not running, so queued work will not dispatch.",
            nextStep: "Restart the backend so the resolver loop starts polling again.",
          },
          {
            code: "missing_codex_worker",
            severity: "warning",
            message: "Start at least one Codex worker to make Codex dispatch possible.",
            nextStep: "Start or re-register a Codex-capable worker.",
          },
        ],
        providers: [
          {
            provider: "claude",
            status: "ready",
            workerCount: 1,
            credentialCount: 1,
            blockingReasons: [],
          },
          {
            provider: "codex",
            status: "blocked",
            workerCount: 0,
            credentialCount: 0,
            blockingReasons: [
              {
                code: "missing_codex_worker",
                severity: "warning",
                message: "Start at least one Codex worker to make Codex dispatch possible.",
                nextStep: "Start or re-register a Codex-capable worker.",
              },
            ],
          },
        ],
        totalWorkerCount: 1,
        totalCredentialCount: 1,
        hasClaudeWorker: true,
        hasCodexWorker: false,
      }}
    />
  );

  assert.match(markup, /Next: Restart the backend/i);
  assert.match(markup, /Next: Start or re-register a Codex-capable worker/i);
});
