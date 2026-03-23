import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { OpenClawTab } from "./openclaw-tab.tsx";

test("OpenClawTab renders the expected provider detail sections", () => {
  const markup = renderToStaticMarkup(
    <OpenClawTab
      detail={{
        artifactInventory: {
          liveTranscript: {
            path: "/Users/tony/.openclaw/agents/main/sessions/primary.jsonl",
            status: "live",
            canonicalSessionId: "primary",
          },
          attachedArchives: [
            {
              kind: "reset_archive",
              path: "/Users/tony/.openclaw/agents/main/sessions/primary.jsonl.reset.2026-03-22T03-00-11.497Z",
            },
          ],
        },
        sessionStore: {
          sessionKey: "agent:main:main",
          origin: "control-ui",
        },
        skills: {
          prompt: "Follow the OpenClaw rollout checklist",
        },
        systemPrompt: {
          workspaceDir: "/Users/tony/Code/helaicopter",
        },
        usageReconciliation: {
          transcriptTotalTokens: 195,
          storeTotalTokens: 275,
        },
        transcriptDiagnostics: {
          eventTypes: {
            customMessage: 1,
          },
        },
        memoryStore: {
          path: "/Users/tony/.openclaw/memory/main.sqlite",
          tables: ["chunks", "files"],
        },
        raw: {
          sessionStoreEntry: {
            sessionId: "primary",
          },
        },
      }}
    />
  );

  assert.match(markup, /Session Overview/);
  assert.match(markup, /Routing And Origin/);
  assert.match(markup, /Skills And Prompt Bootstrap/);
  assert.match(markup, /System Prompt/);
  assert.match(markup, /Usage Reconciliation/);
  assert.match(markup, /Transcript Diagnostics/);
  assert.match(markup, /Memory Store/);
  assert.match(markup, /Artifact Inventory/);
  assert.match(markup, /Raw Payloads/);
  assert.match(markup, /reset_archive/);
  assert.match(markup, /OpenClaw rollout checklist/);
});
