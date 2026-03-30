import type { ConversationPlan, FrontendProvider } from "@/lib/types";

type RawTaskRecord = Record<string, unknown>;

export interface ConversationTaskDagNode {
  id: string;
  taskId: string;
  title: string;
  status?: string;
  dependsOn: string[];
  source: "task" | "plan";
}

export interface ConversationTaskDagEdge {
  id: string;
  source: string;
  target: string;
  inferred: boolean;
}

export interface ConversationTaskDagStats {
  totalNodes: number;
  totalEdges: number;
  completedNodes: number;
}

export interface ConversationTaskDag {
  source: "tasks" | "codex-plan" | "none";
  nodes: ConversationTaskDagNode[];
  edges: ConversationTaskDagEdge[];
  stats: ConversationTaskDagStats;
}

export function buildConversationTaskDag({
  provider,
  tasks,
  plans,
}: {
  provider: FrontendProvider;
  tasks: unknown[];
  plans: ConversationPlan[];
}): ConversationTaskDag {
  const taskNodes = normalizeRawTasks(tasks);
  if (taskNodes.length > 0) {
    return finalizeDag("tasks", taskNodes);
  }

  if (provider === "codex") {
    const planNodes = normalizeCodexPlanTasks(plans);
    if (planNodes.length > 0) {
      return finalizeDag("codex-plan", planNodes);
    }
  }

  return {
    source: "none",
    nodes: [],
    edges: [],
    stats: {
      totalNodes: 0,
      totalEdges: 0,
      completedNodes: 0,
    },
  };
}

function finalizeDag(
  source: ConversationTaskDag["source"],
  nodes: ConversationTaskDagNode[]
): ConversationTaskDag {
  const edges = buildEdges(nodes);
  return {
    source,
    nodes,
    edges,
    stats: {
      totalNodes: nodes.length,
      totalEdges: edges.length,
      completedNodes: nodes.filter((node) => isCompletedStatus(node.status)).length,
    },
  };
}

function normalizeRawTasks(tasks: unknown[]): ConversationTaskDagNode[] {
  return tasks.flatMap((task, index) => {
    const item = asRecord(task);
    const title = stringField(item.title) || stringField(item.step) || `Task ${index + 1}`;
    const taskId =
      stringField(item.taskId) ||
      stringField(item.task_id) ||
      stringField(item.id) ||
      slugify(title) ||
      `task-${index + 1}`;
    const dependsOn = dedupeStrings([
      ...readDependencyIds(item.dependsOn),
      ...readDependencyIds(item.depends_on),
      ...readDependencyIds(item.dependencies),
    ]);
    return [
      {
        id: taskId,
        taskId,
        title,
        status: stringField(item.status),
        dependsOn,
        source: "task" as const,
      },
    ];
  });
}

function normalizeCodexPlanTasks(plans: ConversationPlan[]): ConversationTaskDagNode[] {
  const latestPlan = [...plans]
    .filter((plan) => plan.provider === "codex" && Array.isArray(plan.steps) && plan.steps.length > 0)
    .sort((a, b) => b.timestamp - a.timestamp)[0];

  if (!latestPlan?.steps?.length) {
    return [];
  }

  return latestPlan.steps.map((step, index) => ({
    id: `${latestPlan.id}-step-${index + 1}`,
    taskId: `${latestPlan.id}-step-${index + 1}`,
    title: step.step || `Step ${index + 1}`,
    status: step.status,
    dependsOn: index > 0 ? [`${latestPlan.id}-step-${index}`] : [],
    source: "plan",
  }));
}

function buildEdges(nodes: ConversationTaskDagNode[]): ConversationTaskDagEdge[] {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const explicitEdges = nodes.flatMap((node) =>
    node.dependsOn.map((dependencyId) => ({
      id: `${dependencyId}->${node.id}`,
      source: dependencyId,
      target: node.id,
      inferred: false,
    }))
  ).filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));

  if (explicitEdges.length > 0) {
    return dedupeEdges(explicitEdges);
  }

  return nodes.slice(1).map((node, index) => ({
    id: `${nodes[index].id}->${node.id}`,
    source: nodes[index].id,
    target: node.id,
    inferred: true,
  }));
}

function readDependencyIds(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (typeof entry === "string" && entry.trim()) {
      return [entry];
    }

    const item = asRecord(entry);
    const taskId =
      stringField(item.taskId) || stringField(item.task_id) || stringField(item.id);
    return taskId ? [taskId] : [];
  });
}

function dedupeStrings(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

function dedupeEdges(edges: ConversationTaskDagEdge[]): ConversationTaskDagEdge[] {
  const byId = new Map<string, ConversationTaskDagEdge>();
  for (const edge of edges) {
    if (!byId.has(edge.id)) {
      byId.set(edge.id, edge);
    }
  }
  return [...byId.values()];
}

function isCompletedStatus(status?: string): boolean {
  return ["completed", "done", "succeeded", "success"].includes(status ?? "");
}

function asRecord(value: unknown): RawTaskRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return {};
  }
  return value as RawTaskRecord;
}

function stringField(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
