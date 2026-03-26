/**
 * Graph-native view model for the Oats v2 runtime.
 *
 * Transforms a normalized OvernightOatsRunRecord into a graph-aware
 * view model with edge coloring, ready-queue highlighting, attempt
 * summaries, and action availability.
 */

import type {
  GraphTaskNode,
  MaterializedRuntimeRun,
  MaterializedDispatchEvent,
  MaterializedTaskAttempt,
  GraphMutation,
  OvernightOatsRunRecord,
  TypedEdge,
  EdgePredicate,
  OrchestrationTaskStatus,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Edge colors by predicate
// ---------------------------------------------------------------------------

const EDGE_COLORS: Record<EdgePredicate, string> = {
  code_ready: "blue",
  pr_created: "teal",
  pr_merged: "green",
  checks_passing: "yellow",
  review_approved: "purple",
  artifact_ready: "gray",
};

// ---------------------------------------------------------------------------
// View model types
// ---------------------------------------------------------------------------

export interface GraphEdgeViewModel {
  fromTask: string;
  toTask: string;
  predicate: EdgePredicate;
  satisfied: boolean;
  color: string;
  style: "solid" | "dashed";
}

export interface GraphNodeViewModel {
  taskId: string;
  kind: string;
  title: string;
  status: OrchestrationTaskStatus;
  agent?: string | null;
  model?: string | null;
  attemptCount: number;
  lastError?: string | null;
  isReady: boolean;
  isDiscovered: boolean;
  discoveredBy?: string | null;
  discoveredTaskCount: number;
  operationCount: number;
}

export interface OatsGraphViewModel {
  nodes: GraphNodeViewModel[];
  edges: GraphEdgeViewModel[];
  readyQueue: string[];
  graphMutationCount: number;
  canRefresh: boolean;
  canResume: boolean;
  sidebar: {
    attempts: MaterializedTaskAttempt[];
    graphMutations: GraphMutation[];
    dispatchEvents: MaterializedDispatchEvent[];
  };
}

// ---------------------------------------------------------------------------
// Builder
// ---------------------------------------------------------------------------

export function buildGraphViewModel(
  run: OvernightOatsRunRecord,
  materialized?: MaterializedRuntimeRun | null
): OatsGraphViewModel {
  const readySet = new Set(run.readyQueue);

  const TERMINAL_STATUSES = new Set<string>(["completed", "failed", "timed_out"]);
  const HAS_FAILED_TASKS = run.nodes.some(
    (n) => n.status === "failed" || n.status === "blocked_by_failure"
  );

  const nodes: GraphNodeViewModel[] = run.nodes.map((node) => ({
    taskId: node.taskId,
    kind: node.kind,
    title: node.title,
    status: node.status,
    agent: node.agent,
    model: node.model,
    attemptCount: node.attemptCount,
    lastError: node.lastAttemptStatus === "failed" ? node.lastAttemptStatus : null,
    isReady: readySet.has(node.taskId),
    isDiscovered: Boolean(node.discoveredBy),
    discoveredBy: node.discoveredBy,
    discoveredTaskCount: node.discoveredTaskCount,
    operationCount: node.operationCount,
  }));

  const edges: GraphEdgeViewModel[] = run.edges.map((edge) => ({
    fromTask: edge.fromTask,
    toTask: edge.toTask,
    predicate: edge.predicate,
    satisfied: edge.satisfied,
    color: EDGE_COLORS[edge.predicate] ?? "gray",
    style: edge.satisfied ? "solid" : "dashed",
  }));

  return {
    nodes,
    edges,
    readyQueue: run.readyQueue,
    graphMutationCount: run.graphMutationCount,
    canRefresh: !TERMINAL_STATUSES.has(run.status),
    canResume: !TERMINAL_STATUSES.has(run.status) && HAS_FAILED_TASKS,
    sidebar: {
      attempts: materialized?.taskAttempts ?? [],
      graphMutations: materialized?.graphMutations ?? run.graphMutations ?? [],
      dispatchEvents: materialized?.dispatchEvents ?? [],
    },
  };
}
