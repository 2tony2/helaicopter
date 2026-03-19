import test from "node:test";
import assert from "node:assert/strict";

import {
  orchestrationPrefectDeployment,
  orchestrationPrefectDeployments,
  orchestrationPrefectFlowRun,
  orchestrationPrefectFlowRuns,
  orchestrationPrefectWorkPools,
  orchestrationPrefectWorkers,
  setBaseUrl,
} from "./endpoints";
import {
  normalizePrefectDeployments,
  normalizePrefectFlowRuns,
  normalizePrefectWorkPools,
  normalizePrefectWorkers,
} from "./normalize";

test("Prefect endpoint builders target backend orchestration routes", () => {
  setBaseUrl("https://api.example.test/");

  assert.equal(
    orchestrationPrefectDeployments(),
    "https://api.example.test/orchestration/prefect/deployments"
  );
  assert.equal(
    orchestrationPrefectDeployment("dep-123"),
    "https://api.example.test/orchestration/prefect/deployments/dep-123"
  );
  assert.equal(
    orchestrationPrefectFlowRuns(),
    "https://api.example.test/orchestration/prefect/flow-runs"
  );
  assert.equal(
    orchestrationPrefectFlowRun("flow-run-123"),
    "https://api.example.test/orchestration/prefect/flow-runs/flow-run-123"
  );
  assert.equal(
    orchestrationPrefectWorkers(),
    "https://api.example.test/orchestration/prefect/workers"
  );
  assert.equal(
    orchestrationPrefectWorkPools(),
    "https://api.example.test/orchestration/prefect/work-pools"
  );
});

test("Prefect normalizers join deployments, flow runs, workers, and local Oats metadata", () => {
  const deployments = normalizePrefectDeployments([
    {
      deployment_id: "dep-123",
      deployment_name: "overnight-oats/frontend",
      flow_id: "flow-123",
      flow_name: "oats-flow",
      work_pool_name: "local-macos",
      work_queue_name: "scheduled",
      status: "ready",
      updated_at: "2026-03-19T09:30:00Z",
      tags: ["frontend", "nightly"],
      oats_metadata: {
        run_title: "Frontend Prefect Dashboard",
        source_path:
          "/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md",
        repo_root: "/Users/tony/Code/helaicopter",
        config_path: "/Users/tony/Code/helaicopter/.oats/config.toml",
        local_metadata_path: null,
        artifact_root: null,
      },
    },
  ]);

  const flowRuns = normalizePrefectFlowRuns([
    {
      flow_run_id: "flow-run-123",
      flow_run_name: "frontend-prefect-dashboard-1",
      deployment_id: "dep-123",
      deployment_name: "overnight-oats/frontend",
      flow_id: "flow-123",
      flow_name: "oats-flow",
      work_pool_name: "local-macos",
      work_queue_name: "scheduled",
      state_type: "RUNNING",
      state_name: "Running",
      created_at: "2026-03-19T10:00:00Z",
      updated_at: "2026-03-19T10:05:00Z",
      oats_metadata: {
        run_title: "Frontend Prefect Dashboard",
        source_path:
          "/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md",
        repo_root: "/Users/tony/Code/helaicopter",
        config_path: "/Users/tony/Code/helaicopter/.oats/config.toml",
        local_metadata_path:
          "/Users/tony/Code/helaicopter/.oats/prefect/flow-runs/flow-run-123/metadata.json",
        artifact_root:
          "/Users/tony/Code/helaicopter/.oats/prefect/flow-runs/flow-run-123",
      },
    },
  ]);

  const workers = normalizePrefectWorkers([
    {
      worker_id: "worker-1",
      worker_name: "mac-mini-01",
      work_pool_name: "local-macos",
      status: "ONLINE",
      last_heartbeat_at: "2026-03-19T10:05:30Z",
    },
  ]);

  assert.deepEqual(deployments[0], {
    deploymentId: "dep-123",
    deploymentName: "overnight-oats/frontend",
    flowId: "flow-123",
    flowName: "oats-flow",
    workPoolName: "local-macos",
    workQueueName: "scheduled",
    status: "ready",
    updatedAt: "2026-03-19T09:30:00Z",
    tags: ["frontend", "nightly"],
    oatsMetadata: {
      runTitle: "Frontend Prefect Dashboard",
      sourcePath:
        "/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md",
      repoRoot: "/Users/tony/Code/helaicopter",
      configPath: "/Users/tony/Code/helaicopter/.oats/config.toml",
      repoLabel: "helaicopter",
      sourceLabel: "2026-03-18-prefect-native-oats-orchestration.md",
      sourceHref:
        "/docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md",
      configHref: "/.oats/config.toml",
    },
  });

  assert.deepEqual(flowRuns[0], {
    flowRunId: "flow-run-123",
    flowRunName: "frontend-prefect-dashboard-1",
    deploymentId: "dep-123",
    deploymentName: "overnight-oats/frontend",
    flowId: "flow-123",
    flowName: "oats-flow",
    workPoolName: "local-macos",
    workQueueName: "scheduled",
    stateType: "RUNNING",
    stateName: "Running",
    createdAt: "2026-03-19T10:00:00Z",
    updatedAt: "2026-03-19T10:05:00Z",
    oatsMetadata: {
      runTitle: "Frontend Prefect Dashboard",
      sourcePath:
        "/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md",
      repoRoot: "/Users/tony/Code/helaicopter",
      configPath: "/Users/tony/Code/helaicopter/.oats/config.toml",
      localMetadataPath:
        "/Users/tony/Code/helaicopter/.oats/prefect/flow-runs/flow-run-123/metadata.json",
      artifactRoot:
        "/Users/tony/Code/helaicopter/.oats/prefect/flow-runs/flow-run-123",
      repoLabel: "helaicopter",
      sourceLabel: "2026-03-18-prefect-native-oats-orchestration.md",
      sourceHref:
        "/docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md",
      configHref: "/.oats/config.toml",
      metadataHref: "/.oats/prefect/flow-runs/flow-run-123/metadata.json",
      artifactHref: "/.oats/prefect/flow-runs/flow-run-123",
    },
    statusTone: "running",
    statusLabel: "Running",
    isActive: true,
  });

  assert.deepEqual(workers[0], {
    workerId: "worker-1",
    workerName: "mac-mini-01",
    workPoolName: "local-macos",
    status: "ONLINE",
    lastHeartbeatAt: "2026-03-19T10:05:30Z",
    statusTone: "healthy",
    isOnline: true,
  });

  const workPools = normalizePrefectWorkPools(
    [
      {
        work_pool_id: "pool-1",
        work_pool_name: "local-macos",
        type: "process",
        status: "READY",
        is_paused: false,
        concurrency_limit: 2,
      },
    ],
    workers
  );

  assert.deepEqual(workPools[0], {
    workPoolId: "pool-1",
    workPoolName: "local-macos",
    type: "process",
    status: "READY",
    isPaused: false,
    concurrencyLimit: 2,
    workerCount: 1,
    onlineWorkerCount: 1,
    statusTone: "healthy",
  });
});
