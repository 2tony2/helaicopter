import { readdir, readFile, stat } from "fs/promises";
import type { Dirent } from "fs";
import { join } from "path";
import { orchestrationResponseCache } from "./cache";
import { OATS_DIR, OVERNIGHT_OATS_DIR, WORKSPACES_DIR } from "./constants";
import type {
  OrchestrationDag,
  OrchestrationDagEdge,
  OrchestrationDagNode,
  OrchestrationInvocation,
  OrchestrationTaskRecord,
  OvernightOatsRunRecord,
} from "./types";
import { isLikelyActive } from "./utils";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`Expected non-empty string for ${field}`);
  }
  return value;
}

function readOptionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function readStringArray(value: unknown, field: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new Error(`Expected string[] for ${field}`);
  }
  return value;
}

function normalizeRepoProjectPath(repoRoot: string, agent: string): string | undefined {
  const encoded = repoRoot.replace(/\//g, "-");
  if (agent === "codex") {
    return `codex:${encoded}`;
  }
  if (agent === "claude") {
    return encoded;
  }
  return undefined;
}

function normalizeInvocation(
  value: unknown,
  repoRoot: string,
  fallback?: { agent: string; role: string }
): OrchestrationInvocation {
  if (!isRecord(value)) {
    if (!fallback) {
      throw new Error("Expected invocation object");
    }
    return {
      agent: fallback.agent,
      role: fallback.role,
      command: [],
      cwd: repoRoot,
      prompt: "",
      sessionId: null,
      sessionIdField: null,
      requestedSessionId: null,
      outputText: "",
      rawStdout: "",
      rawStderr: "",
      exitCode: 0,
      timedOut: false,
      startedAt: "",
      finishedAt: "",
    };
  }

  const agent = readString(value.agent, "invocation.agent");
  const sessionId = readOptionalString(value.session_id);
  const projectPath = sessionId
    ? normalizeRepoProjectPath(repoRoot, agent)
    : undefined;

  return {
    agent,
    role: readString(value.role, "invocation.role"),
    command: readStringArray(value.command, "invocation.command"),
    cwd: readString(value.cwd, "invocation.cwd"),
    prompt: readString(value.prompt, "invocation.prompt"),
    sessionId,
    sessionIdField: readOptionalString(value.session_id_field),
    requestedSessionId: readOptionalString(value.requested_session_id),
    outputText: typeof value.output_text === "string" ? value.output_text : "",
    rawStdout: typeof value.raw_stdout === "string" ? value.raw_stdout : "",
    rawStderr: typeof value.raw_stderr === "string" ? value.raw_stderr : "",
    exitCode:
      typeof value.exit_code === "number"
        ? value.exit_code
        : Number(value.exit_code ?? 0),
    timedOut: Boolean(value.timed_out),
    startedAt: readOptionalString(value.started_at) ?? "",
    finishedAt: readOptionalString(value.finished_at) ?? "",
    projectPath,
    conversationPath:
      projectPath && sessionId
        ? `/conversations/${encodeURIComponent(projectPath)}/${sessionId}`
        : undefined,
  };
}

function normalizeTaskRecords(
  value: unknown,
  repoRoot: string
): OrchestrationTaskRecord[] {
  if (!Array.isArray(value)) {
    throw new Error("Expected tasks array");
  }

  const tasks = value.map((task, index) => {
    if (!isRecord(task)) {
      throw new Error(`Expected task object at index ${index}`);
    }

    return {
      taskId: readString(task.task_id, `tasks[${index}].task_id`),
      title: readString(task.title, `tasks[${index}].title`),
      dependsOn: readStringArray(
        task.depends_on ?? [],
        `tasks[${index}].depends_on`
      ),
      status:
        (readOptionalString(task.status) as OrchestrationTaskRecord["status"]) ??
        (isRecord(task.invocation)
          ? Boolean(task.invocation.timed_out)
            ? "timed_out"
            : Number(task.invocation.exit_code ?? 0) === 0
            ? "succeeded"
            : "failed"
          : "pending"),
      attempts:
        typeof task.attempts === "number"
          ? task.attempts
          : Number(task.attempts ?? 0),
      invocation: normalizeInvocation(task.invocation, repoRoot, {
        agent:
          readOptionalString(task.agent) ??
          (isRecord(task.invocation) ? readString(task.invocation.agent, "invocation.agent") : "executor"),
        role:
          readOptionalString(task.role) ??
          (isRecord(task.invocation) ? readString(task.invocation.role, "invocation.role") : "executor"),
      }),
    } satisfies OrchestrationTaskRecord;
  });

  const taskIds = new Set(tasks.map((task) => task.taskId));
  if (taskIds.size !== tasks.length) {
    throw new Error("Duplicate task ids found in Oats run");
  }

  for (const task of tasks) {
    for (const dependency of task.dependsOn) {
      if (!taskIds.has(dependency)) {
        throw new Error(
          `Task '${task.taskId}' depends on unknown task '${dependency}'`
        );
      }
    }
  }

  return tasks;
}

function buildOrchestrationDag(
  planner: OrchestrationInvocation | null,
  tasks: OrchestrationTaskRecord[],
  runTitle: string,
  options?: {
    runStatus?: OvernightOatsRunRecord["status"];
    activeTaskId?: string | null;
    heartbeatAt?: string | null;
  }
): OrchestrationDag {
  const nodes = new Map<string, OrchestrationDagNode>();
  const edges = new Map<string, OrchestrationDagEdge>();
  const activeTaskId = options?.activeTaskId ?? null;
  const runStatus = options?.runStatus ?? "completed";
  const heartbeatAt = options?.heartbeatAt ?? null;

  if (planner) {
    nodes.set("planner", {
      id: "planner",
      kind: "planner",
      label: "Planner",
      description: runTitle,
      role: planner.role,
      agent: planner.agent,
      sessionId: planner.sessionId,
      projectPath: planner.projectPath,
      conversationPath: planner.conversationPath,
      status: runStatus === "planning" ? "running" : runStatus,
      isActive: runStatus === "planning",
      lastHeartbeatAt: heartbeatAt,
      exitCode: planner.exitCode,
      timedOut: planner.timedOut,
      depth: 0,
    });
  }

  for (const task of tasks) {
    nodes.set(task.taskId, {
      id: task.taskId,
      kind: "task",
      label: task.taskId,
      description: task.title,
      role: task.invocation.role,
      agent: task.invocation.agent,
      sessionId: task.invocation.sessionId,
      projectPath: task.invocation.projectPath,
      conversationPath: task.invocation.conversationPath,
      status: task.status,
      isActive: activeTaskId === task.taskId || task.status === "running",
      attempts: task.attempts,
      lastHeartbeatAt: heartbeatAt,
      exitCode: task.invocation.exitCode,
      timedOut: task.invocation.timedOut,
      depth: planner ? 1 : 0,
    });
  }

  for (const task of tasks) {
    if (task.dependsOn.length === 0 && planner) {
      const edgeId = `planner->${task.taskId}`;
      edges.set(edgeId, {
        id: edgeId,
        source: "planner",
        target: task.taskId,
        label: "dispatches",
      });
    }

    for (const dependency of task.dependsOn) {
      const edgeId = `${dependency}->${task.taskId}`;
      edges.set(edgeId, {
        id: edgeId,
        source: dependency,
        target: task.taskId,
        label: "depends_on",
      });
    }
  }

  const indegree = new Map<string, number>();
  const children = new Map<string, string[]>();

  for (const nodeId of nodes.keys()) {
    indegree.set(nodeId, 0);
    children.set(nodeId, []);
  }

  for (const edge of edges.values()) {
    indegree.set(edge.target, (indegree.get(edge.target) || 0) + 1);
    children.set(edge.source, [...(children.get(edge.source) || []), edge.target]);
  }

  const queue = Array.from(nodes.values())
    .filter((node) => (indegree.get(node.id) || 0) === 0)
    .map((node) => node.id);

  while (queue.length > 0) {
    const currentId = queue.shift();
    if (!currentId) break;
    const current = nodes.get(currentId);
    if (!current) continue;

    for (const childId of children.get(currentId) || []) {
      const child = nodes.get(childId);
      if (!child) continue;
      if (child.depth < current.depth + 1) {
        child.depth = current.depth + 1;
        nodes.set(childId, child);
      }
      indegree.set(childId, (indegree.get(childId) || 0) - 1);
      if ((indegree.get(childId) || 0) === 0) {
        queue.push(childId);
      }
    }
  }

  const orderedNodes = Array.from(nodes.values()).sort((a, b) => {
    if (a.depth !== b.depth) {
      return a.depth - b.depth;
    }
    return a.id.localeCompare(b.id);
  });
  const orderedEdges = Array.from(edges.values()).sort((a, b) =>
    a.id.localeCompare(b.id)
  );

  const breadthMap = new Map<number, number>();
  const providerBreakdown: Record<string, number> = {};
  for (const node of orderedNodes) {
    breadthMap.set(node.depth, (breadthMap.get(node.depth) || 0) + 1);
    providerBreakdown[node.agent] = (providerBreakdown[node.agent] || 0) + 1;
  }

  return {
    nodes: orderedNodes,
    edges: orderedEdges,
    stats: {
      totalNodes: orderedNodes.length,
      totalEdges: orderedEdges.length,
      maxDepth: Math.max(0, ...orderedNodes.map((node) => node.depth)),
      maxBreadth: Math.max(0, ...breadthMap.values()),
      rootCount: orderedNodes.filter((node) =>
        !orderedEdges.some((edge) => edge.target === node.id)
      ).length,
      providerBreakdown,
      timedOutCount: orderedNodes.filter((node) => node.timedOut).length,
      activeCount: orderedNodes.filter((node) => node.isActive).length,
      pendingCount: orderedNodes.filter((node) => node.status === "pending").length,
      failedCount: orderedNodes.filter((node) => node.status === "failed").length,
      succeededCount: orderedNodes.filter((node) => node.status === "succeeded").length,
    },
  };
}

function parseOvernightOatsRunRecord(
  raw: unknown,
  filePath: string,
  fileMtimeMs: number
): OvernightOatsRunRecord {
  if (!isRecord(raw)) {
    throw new Error("Expected Oats run record object");
  }

  const repoRoot = readString(raw.repo_root, "repo_root");
  const planner =
    raw.planner === null || raw.planner === undefined
      ? null
      : normalizeInvocation(raw.planner, repoRoot);
  const tasks = normalizeTaskRecords(raw.tasks, repoRoot);
  const runTitle = readString(raw.run_title, "run_title");

  return {
    source: "overnight-oats",
    contractVersion: "oats-run-v1",
    runId:
      readOptionalString(raw.run_id) ??
      readString(raw.record_path ?? filePath, "record_path"),
    runTitle,
    repoRoot,
    configPath: readString(raw.config_path, "config_path"),
    runSpecPath: readString(raw.run_spec_path, "run_spec_path"),
    mode: readString(raw.mode, "mode"),
    integrationBranch: readString(raw.integration_branch, "integration_branch"),
    taskPrTarget: readString(raw.task_pr_target, "task_pr_target"),
    finalPrTarget: readString(raw.final_pr_target, "final_pr_target"),
    status: isLikelyActive(fileMtimeMs) ? "running" : "completed",
    activeTaskId: null,
    heartbeatAt: new Date(fileMtimeMs).toISOString(),
    finishedAt: readString(raw.recorded_at, "recorded_at"),
    planner,
    tasks,
    createdAt: readString(raw.recorded_at, "recorded_at"),
    lastUpdatedAt: new Date(fileMtimeMs).toISOString(),
    isRunning: isLikelyActive(fileMtimeMs),
    recordedAt: readString(raw.recorded_at, "recorded_at"),
    recordPath:
      typeof raw.record_path === "string" && raw.record_path.trim()
        ? raw.record_path
        : filePath,
    dag: buildOrchestrationDag(planner, tasks, runTitle, {
      runStatus: isLikelyActive(fileMtimeMs) ? "running" : "completed",
      heartbeatAt: new Date(fileMtimeMs).toISOString(),
    }),
  };
}

function parseOvernightOatsRuntimeState(
  raw: unknown,
  filePath: string,
  fileMtimeMs: number
): OvernightOatsRunRecord {
  if (!isRecord(raw)) {
    throw new Error("Expected Oats runtime state object");
  }

  const repoRoot = readString(raw.repo_root, "repo_root");
  const planner =
    raw.planner === null || raw.planner === undefined
      ? null
      : normalizeInvocation(raw.planner, repoRoot);
  const tasks = normalizeTaskRecords(raw.tasks, repoRoot);
  const runTitle = readString(raw.run_title, "run_title");
  const status = readString(
    raw.status,
    "status"
  ) as OvernightOatsRunRecord["status"];
  const heartbeatAt =
    readOptionalString(raw.heartbeat_at) ?? new Date(fileMtimeMs).toISOString();

  return {
    source: "overnight-oats",
    contractVersion: "oats-runtime-v1",
    runId: readString(raw.run_id, "run_id"),
    runTitle,
    repoRoot,
    configPath: readString(raw.config_path, "config_path"),
    runSpecPath: readString(raw.run_spec_path, "run_spec_path"),
    mode: readString(raw.mode, "mode"),
    integrationBranch: readString(raw.integration_branch, "integration_branch"),
    taskPrTarget: readString(raw.task_pr_target, "task_pr_target"),
    finalPrTarget: readString(raw.final_pr_target, "final_pr_target"),
    status,
    activeTaskId: readOptionalString(raw.active_task_id),
    heartbeatAt,
    finishedAt: readOptionalString(raw.finished_at),
    planner,
    tasks,
    createdAt: readString(raw.started_at, "started_at"),
    lastUpdatedAt:
      readOptionalString(raw.updated_at) ?? new Date(fileMtimeMs).toISOString(),
    isRunning:
      status === "planning" ||
      status === "running" ||
      (status === "pending" && isLikelyActive(fileMtimeMs)),
    recordedAt:
      readOptionalString(raw.updated_at) ?? new Date(fileMtimeMs).toISOString(),
    recordPath: filePath,
    dag: buildOrchestrationDag(planner, tasks, runTitle, {
      runStatus: status,
      activeTaskId: readOptionalString(raw.active_task_id),
      heartbeatAt,
    }),
  };
}

async function listOatsRunFiles(): Promise<string[]> {
  const files = new Set<string>();

  async function collectJsonFiles(dir: string, maxDepth: number): Promise<void> {
    async function walk(currentDir: string, depth: number): Promise<void> {
      let entries;
      try {
        entries = await readdir(currentDir, { withFileTypes: true });
      } catch {
        return;
      }

      for (const entry of entries) {
        const fullPath = join(currentDir, entry.name);
        if (entry.isFile() && entry.name.endsWith(".json")) {
          files.add(fullPath);
          continue;
        }
        if (entry.isDirectory() && depth < maxDepth) {
          await walk(fullPath, depth + 1);
        }
      }
    }

    await walk(dir, 0);
  }

  let entries: Dirent[] = [];
  try {
    entries = await readdir(WORKSPACES_DIR, { withFileTypes: true });
  } catch {
    entries = [];
  }

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    await collectJsonFiles(join(WORKSPACES_DIR, entry.name, ".oats", "runs"), 1);
    await collectJsonFiles(join(WORKSPACES_DIR, entry.name, ".oats", "pr-runs"), 1);
    await collectJsonFiles(join(WORKSPACES_DIR, entry.name, ".oats", "runtime"), 2);
  }

  await collectJsonFiles(OATS_DIR, 4);
  await collectJsonFiles(OVERNIGHT_OATS_DIR, 4);

  return Array.from(files);
}

export async function listOvernightOatsRuns(): Promise<OvernightOatsRunRecord[]> {
  const runs = await orchestrationResponseCache.getOrLoad("oats-runs", 5_000, async () => {
    const files = await listOatsRunFiles();
    const runsById = new Map<string, OvernightOatsRunRecord>();

    for (const filePath of files) {
      try {
        const content = await readFile(filePath, "utf-8");
        const fileStats = await stat(filePath).catch(() => null);
        const raw = JSON.parse(content);
        const parsed =
          isRecord(raw) && raw.contract_version === "oats-runtime-v1"
            ? parseOvernightOatsRuntimeState(
                raw,
                filePath,
                fileStats?.mtimeMs ?? Date.now()
              )
            : parseOvernightOatsRunRecord(
                raw,
                filePath,
                fileStats?.mtimeMs ?? Date.now()
              );
        const existing = runsById.get(parsed.runId);
        if (
          !existing ||
          (parsed.isRunning && !existing.isRunning) ||
          new Date(parsed.lastUpdatedAt).getTime() >
            new Date(existing.lastUpdatedAt).getTime()
        ) {
          runsById.set(parsed.runId, parsed);
        }
      } catch {
        continue;
      }
    }

    return Array.from(runsById.values()).sort((a, b) =>
      new Date(b.lastUpdatedAt).getTime() - new Date(a.lastUpdatedAt).getTime()
    );
  });

  return runs as OvernightOatsRunRecord[];
}
