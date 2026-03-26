import assert from "node:assert/strict";
import test from "node:test";
import React from "react";

import OrchestrationPage from "./page";
import { OrchestrationHub } from "@/components/orchestration/orchestration-hub";

test("OrchestrationPage resolves promise-based searchParams before reading the tab", async () => {
  const page = await OrchestrationPage({
    searchParams: Promise.resolve({ tab: "conversation-dags" }),
  });

  assert.ok(React.isValidElement(page));
  assert.equal(page.type, OrchestrationHub);
  assert.equal(page.props.initialTab, "conversation-dags");
});
