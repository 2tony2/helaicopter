import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type {
  AuthCredential,
  DispatchHistoryEntry,
  DispatchQueueSnapshot,
  Worker,
} from "@/lib/types";
import {
  AddCredentialDialog,
  AuthManagementSection,
} from "@/components/auth/auth-management-section";
import { QueueMonitorSection } from "@/components/dispatch/queue-monitor";
import {
  WorkerDashboardSection,
  buildWorkerDashboardModel,
} from "./worker-dashboard";

function buildWorkers(): Worker[] {
  return [
    {
      workerId: "wkr_claude_idle",
      workerType: "pi_shell",
      provider: "claude",
      capabilities: {
        provider: "claude",
        models: ["claude-sonnet-4-6"],
        maxConcurrentTasks: 1,
        supportsDiscovery: true,
        supportsResume: true,
        tags: ["local"],
      },
      host: "local",
      pid: 1201,
      worktreeRoot: "/tmp/claude",
      registeredAt: "2026-03-26T09:00:00Z",
      lastHeartbeatAt: "2026-03-26T09:10:00Z",
      status: "idle",
      currentTaskId: null,
      currentRunId: null,
    },
    {
      workerId: "wkr_codex_busy",
      workerType: "codex_session",
      provider: "codex",
      capabilities: {
        provider: "codex",
        models: ["o3-pro"],
        maxConcurrentTasks: 1,
        supportsDiscovery: false,
        supportsResume: false,
        tags: ["gpu"],
      },
      host: "pi-2",
      pid: 2202,
      worktreeRoot: "/tmp/codex",
      registeredAt: "2026-03-26T09:01:00Z",
      lastHeartbeatAt: "2026-03-26T09:09:30Z",
      status: "busy",
      currentTaskId: "task-auth",
      currentRunId: "run-1",
    },
    {
      workerId: "wkr_claude_auth",
      workerType: "pi_shell",
      provider: "claude",
      capabilities: {
        provider: "claude",
        models: ["claude-opus-4-6"],
        maxConcurrentTasks: 1,
        supportsDiscovery: true,
        supportsResume: true,
        tags: [],
      },
      host: "pi-3",
      pid: 3303,
      worktreeRoot: null,
      registeredAt: "2026-03-26T09:02:00Z",
      lastHeartbeatAt: "2026-03-26T08:58:00Z",
      status: "auth_expired",
      currentTaskId: null,
      currentRunId: null,
    },
  ];
}

function buildCredentials(): AuthCredential[] {
  return [
    {
      credentialId: "cred_claude_active",
      provider: "claude",
      credentialType: "api_key",
      status: "active",
      tokenExpiresAt: "2026-04-01T00:00:00Z",
      cliConfigPath: null,
      subscriptionId: null,
      subscriptionTier: null,
      rateLimitTier: "pro",
      createdAt: "2026-03-20T08:00:00Z",
      lastUsedAt: "2026-03-26T09:00:00Z",
      lastRefreshedAt: null,
      cumulativeCostUsd: 2.5,
      costSinceReset: 1.25,
    },
    {
      credentialId: "cred_codex_revoked",
      provider: "codex",
      credentialType: "oauth_token",
      status: "revoked",
      tokenExpiresAt: "2026-03-26T08:00:00Z",
      cliConfigPath: null,
      subscriptionId: "sub_123",
      subscriptionTier: "team",
      rateLimitTier: "burst",
      createdAt: "2026-03-19T08:00:00Z",
      lastUsedAt: null,
      lastRefreshedAt: "2026-03-25T20:00:00Z",
      cumulativeCostUsd: 7.75,
      costSinceReset: 0,
    },
  ];
}

function buildQueueSnapshot(): DispatchQueueSnapshot {
  return {
    ready: [
      { runId: "run-1", taskId: "task-auth", provider: "claude", model: "claude-sonnet-4-6" },
    ],
    deferred: [
      {
        runId: "run-2",
        taskId: "task-ui",
        provider: "codex",
        model: "o3-pro",
        reason: "auth_expired",
      },
    ],
  };
}

function buildDispatchHistory(): DispatchHistoryEntry[] {
  return [
    {
      runId: "run-1",
      taskId: "task-auth",
      workerId: "wkr_codex_busy",
      provider: "codex",
      model: "o3-pro",
      dispatchedAt: "2026-03-26T09:09:00Z",
    },
  ];
}

test("buildWorkerDashboardModel summarizes provider groups and auth issues", () => {
  const dashboard = buildWorkerDashboardModel(buildWorkers());

  assert.equal(dashboard.summary.total, 3);
  assert.equal(dashboard.summary.idle, 1);
  assert.equal(dashboard.summary.busy, 1);
  assert.equal(dashboard.summary.authExpired, 1);
  assert.equal(dashboard.providerGroups[0]?.provider, "claude");
  assert.equal(dashboard.providerGroups[0]?.workers.length, 2);
  assert.ok(dashboard.hasAuthIssues);
});

test("operator UI sections render worker, auth, and queue monitoring content", () => {
  const markup = renderToStaticMarkup(
    <div>
      <WorkerDashboardSection workers={buildWorkers()} />
      <AuthManagementSection credentials={buildCredentials()} />
      <QueueMonitorSection
        snapshot={buildQueueSnapshot()}
        history={buildDispatchHistory()}
      />
      <AddCredentialDialog />
    </div>
  );

  assert.match(markup, /Worker Dashboard/);
  assert.match(markup, /Auth Management/);
  assert.match(markup, /Queue Monitor/);
  assert.match(markup, /auth_expired/);
  assert.match(markup, /Drain worker/);
  assert.match(markup, /Revoke/);
  assert.match(markup, /Add credential/);
  assert.match(markup, /Recent dispatches/);
});
