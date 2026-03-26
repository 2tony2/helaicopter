import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type {
  AuthCredential,
  DispatchHistoryEntry,
  DispatchQueueSnapshot,
  ProviderReadiness,
  Worker,
} from "@/lib/types";
import {
  AddCredentialDialog,
  AuthManagementSection,
} from "@/components/auth/auth-management-section";
import { QueueMonitorSection } from "@/components/dispatch/queue-monitor";
import { OperatorBootstrapPanel } from "@/components/orchestration/operator-bootstrap-panel";
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
      readinessReason: null,
      currentTaskId: null,
      currentRunId: null,
      providerSessionId: "sess_claude_ready",
      sessionStatus: "ready",
      sessionStartedAt: "2026-03-26T09:00:00Z",
      sessionLastUsedAt: "2026-03-26T09:10:00Z",
      sessionFailureReason: null,
      sessionResetAvailable: true,
      sessionResetRequestedAt: null,
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
      readinessReason: null,
      currentTaskId: "task-auth",
      currentRunId: "run-1",
      providerSessionId: "sess_codex_busy",
      sessionStatus: "ready",
      sessionStartedAt: "2026-03-26T09:01:00Z",
      sessionLastUsedAt: "2026-03-26T09:09:30Z",
      sessionFailureReason: null,
      sessionResetAvailable: true,
      sessionResetRequestedAt: null,
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
      readinessReason: "Worker auth has expired and must be refreshed.",
      currentTaskId: null,
      currentRunId: null,
      providerSessionId: null,
      sessionStatus: "failed",
      sessionStartedAt: null,
      sessionLastUsedAt: null,
      sessionFailureReason: "Provider session bootstrap failed.",
      sessionResetAvailable: true,
      sessionResetRequestedAt: null,
    },
  ];
}

function buildCredentials(): AuthCredential[] {
  return [
    {
      credentialId: "cred_claude_active",
      provider: "claude",
      credentialType: "local_cli_session",
      status: "active",
      providerStatusCode: "ready",
      providerStatusMessage: "Credential is ready for provider execution.",
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
      providerStatusCode: "revoked",
      providerStatusMessage: "Credential has been revoked.",
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

function buildProviderReadiness(): ProviderReadiness[] {
  return [
    {
      provider: "claude",
      status: "ready",
      healthyWorkerCount: 2,
      readyWorkerCount: 1,
      activeCredentialCount: 1,
      blockingReasons: [],
    },
    {
      provider: "codex",
      status: "blocked",
      healthyWorkerCount: 0,
      readyWorkerCount: 0,
      activeCredentialCount: 0,
      blockingReasons: [
        {
          code: "missing_cli_session",
          severity: "error",
          message: "Local CLI session metadata is missing for this provider credential.",
        },
      ],
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
        reasonLabel: "A matching worker exists, but its provider auth must be refreshed.",
        canRetry: false,
      },
    ],
  };
}

function buildBootstrapSummary() {
  return {
    overallStatus: "blocked" as const,
    resolverRunning: true,
    blockingReasons: [
      {
        code: "missing_codex_worker",
        severity: "warning",
        message: "Start at least one Codex worker to make Codex dispatch possible.",
        nextStep: "Start or re-register a Codex-capable worker.",
      },
    ],
    providers: [
      { provider: "claude" as const, status: "ready" as const, workerCount: 1, credentialCount: 1, blockingReasons: [] },
      {
        provider: "codex" as const,
        status: "blocked" as const,
        workerCount: 0,
        credentialCount: 0,
        blockingReasons: [
          {
            code: "missing_cli_session",
            severity: "error" as const,
            message: "Local CLI session metadata is missing for this provider credential.",
            nextStep: null,
          },
        ],
      },
    ],
    totalWorkerCount: 1,
    totalCredentialCount: 1,
    hasClaudeWorker: true,
    hasCodexWorker: false,
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

test("worker dashboard surfaces provider readiness and remediation copy", () => {
  const markup = renderToStaticMarkup(
    <WorkerDashboardSection
      workers={buildWorkers()}
      providerReadiness={buildProviderReadiness()}
    />
  );

  assert.match(markup, /Local CLI session metadata is missing/i);
  assert.match(markup, /0 active credentials/i);
});

test("worker dashboard renders session state and reset affordance", () => {
  const markup = renderToStaticMarkup(
    <WorkerDashboardSection
      workers={buildWorkers()}
      providerReadiness={buildProviderReadiness()}
      onResetSession={() => undefined}
    />
  );

  assert.match(markup, /session ready/i);
  assert.match(markup, /provider session bootstrap failed/i);
  assert.match(markup, /reset session/i);
});

test("operator UI sections render worker, auth, and queue monitoring content", () => {
  const markup = renderToStaticMarkup(
    <div>
      <OperatorBootstrapPanel summary={buildBootstrapSummary()} />
      <WorkerDashboardSection workers={buildWorkers()} providerReadiness={buildProviderReadiness()} />
      <AuthManagementSection credentials={buildCredentials()} />
      <QueueMonitorSection
        snapshot={buildQueueSnapshot()}
        history={buildDispatchHistory()}
      />
      <AddCredentialDialog />
    </div>
  );

  assert.match(markup, /Bootstrap Checklist/);
  assert.match(markup, /Start a Claude worker/);
  assert.match(markup, /Start a Codex worker/);
  assert.match(markup, /Worker Dashboard/);
  assert.match(markup, /Auth Management/);
  assert.match(markup, /Queue Monitor/);
  assert.match(markup, /credential refresh/i);
  assert.match(markup, /Local CLI session metadata is missing/i);
  assert.match(markup, /Drain worker/);
  assert.match(markup, /Revoke/);
  assert.match(markup, /Add credential/);
  assert.match(markup, /Recent dispatches/);
  assert.match(markup, /provider auth must be refreshed/i);
});
