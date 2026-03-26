"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import {
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
  Handle,
  Position,
  type NodeProps,
} from "@xyflow/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthManagementPanel } from "@/components/auth/auth-management-section";
import { QueueMonitorPanel } from "@/components/dispatch/queue-monitor";
import { OperatorBootstrapPanelContainer } from "@/components/orchestration/operator-bootstrap-panel";
import { WorkerDashboardPanel } from "@/components/workers/worker-dashboard";
import { getLayoutedElements } from "@/lib/conversation-dag-layout";
import {
  cancelOvernightOatsTask,
  forceRetryOvernightOatsTask,
  insertOvernightOatsTask,
  pauseOvernightOatsRun,
  refreshOvernightOatsRun,
  rerouteOvernightOatsTask,
  resumeOvernightOatsRun,
} from "@/lib/client/mutations";
import { useOvernightOatsRuns } from "@/hooks/use-conversations";
import { requestJson } from "@/lib/client/fetcher";
import * as endpoints from "@/lib/client/endpoints";
import { normalizeRuntimeMaterializedRun } from "@/lib/client/normalize";
import type {
  MaterializedRuntimeRun,
  OrchestrationDagNode,
  OrchestrationStatusTone,
  OvernightOatsRunRecord,
} from "@/lib/types";
import { OatsPrStack } from "./oats-pr-stack";
import { buildOatsViewModel } from "./oats-view-model";
import {
  Activity,
  Bot,
  CheckCircle2,
  Clock3,
  ExternalLink,
  GitBranch,
  Layers2,
  Network,
  PlaySquare,
  Route,
  CircleAlert,
  ShieldAlert,
  TimerOff,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { cn } from "@/lib/utils";
import { memo } from "react";

interface OatsNodeData {
  label: string;
  description?: string;
  role: string;
  agent: string;
  status: string;
  statusLabel: string;
  statusTone: OrchestrationStatusTone;
  isActive: boolean;
  isStale: boolean;
  timedOut: boolean;
  exitCode?: number | null;
  depth: number;
  attempts?: number;
  selectable: boolean;
  isSelected: boolean;
  threadHref?: string;
  prState?: string;
  mergeGateStatus?: string;
  onSelect: () => void;
  onOpenThread?: () => void;
}

const OATS_NODE_WIDTH = 280;
const OATS_NODE_LAYOUT_HEIGHT = 236;
const OATS_STALE_AFTER_MS = 300_000;

function humanizeToken(value?: string | null) {
  if (!value) return "unknown";
  return value.replace(/_/g, " ");
}

function isStaleHeartbeat(timestamp?: string | null, active = false) {
  if (!active || !timestamp) return false;
  return Date.now() - new Date(timestamp).getTime() > OATS_STALE_AFTER_MS;
}

function deriveOatsNodeTone(node: OrchestrationDagNode, isStale: boolean): OrchestrationStatusTone {
  if (node.statusTone) return node.statusTone;
  if (isStale) return "warning";
  if (node.isActive) return "running";
  if (node.status === "succeeded" || node.status === "completed") return "success";
  if (node.status === "failed" || node.status === "timed_out") return "error";
  if (node.status === "pending" || node.status === "planning" || node.status === "blocked") {
    return "pending";
  }
  return "unknown";
}

function deriveOatsNodeLabel(node: OrchestrationDagNode, isStale: boolean): string {
  if (node.statusLabel) return node.statusLabel;
  if (isStale) return "stale";
  if (node.timedOut) return "timed out";
  return node.status;
}

function replaceRunRecord(
  current: OvernightOatsRunRecord[] | undefined,
  nextRun: OvernightOatsRunRecord
) {
  const runs = current ?? [];
  const nextRuns = runs.some((run) => run.runId === nextRun.runId)
    ? runs.map((run) => (run.runId === nextRun.runId ? nextRun : run))
    : [nextRun, ...runs];

  return [...nextRuns].sort(
    (a, b) =>
      new Date(b.lastUpdatedAt).getTime() - new Date(a.lastUpdatedAt).getTime()
  );
}

const OatsNode = memo(function OatsNode({ data }: NodeProps) {
  const d = data as unknown as OatsNodeData;
  const isPlanner = d.role === "planner";
  const statusToneClass = d.statusTone === "warning"
    ? "border-amber-500/70 ring-2 ring-amber-500/30"
    : d.statusTone === "running"
    ? "border-emerald-500/80 ring-4 ring-emerald-500/20 animate-pulse"
    : d.statusTone === "success"
    ? "border-emerald-500/40 ring-1 ring-emerald-500/10"
    : d.statusTone === "error"
    ? "border-rose-500/50 ring-1 ring-rose-500/15"
    : "border-sky-500/40 ring-1 ring-sky-500/10";

  return (
    <div
      className={cn(
        "nodrag flex w-[280px] min-h-[236px] flex-col overflow-hidden rounded-2xl border-2 bg-card text-card-foreground shadow-lg transition-all hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        d.selectable ? "cursor-pointer hover:scale-[1.02]" : "",
        isPlanner ? "bg-slate-50/70 dark:bg-slate-950/20" : "",
        d.isSelected ? "border-primary ring-4 ring-primary/20" : "",
        statusToneClass
      )}
      onClick={d.onSelect}
      role={d.selectable ? "button" : undefined}
      tabIndex={d.selectable ? 0 : -1}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          d.onSelect();
        }
      }}
    >
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-background !bg-muted-foreground" />
      <div
        className={cn(
          "border-b px-4 py-3",
          isPlanner ? "bg-slate-500/10 border-slate-500/15" : "bg-sky-500/10 border-sky-500/15"
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1 min-w-0">
            <div className="line-clamp-2 text-sm font-semibold">{d.label}</div>
            {d.description && (
              <div className="line-clamp-2 text-xs text-muted-foreground">
                {d.description}
              </div>
            )}
          </div>
          <Badge variant={isPlanner ? "default" : "secondary"}>{d.role}</Badge>
        </div>
      </div>
      <div className="flex flex-1 flex-col p-4">
        <div className="grid flex-1 grid-cols-2 auto-rows-fr gap-2 text-xs">
          <div className="rounded-lg border border-border/50 bg-muted/50 px-2.5 py-2">
            <div className="text-muted-foreground">Agent</div>
            <div className="mt-1 font-medium">{d.agent}</div>
          </div>
          <div className="rounded-lg border border-border/50 bg-muted/50 px-2.5 py-2">
            <div className="text-muted-foreground">Status</div>
            <div className="mt-1 flex items-center gap-1 font-medium">
              {d.statusTone === "running" ? (
                <Activity className="h-3 w-3 text-emerald-500" />
              ) : d.statusTone === "success" ? (
                <CheckCircle2 className="h-3 w-3 text-emerald-500" />
              ) : d.statusTone === "error" || d.statusTone === "warning" ? (
                <CircleAlert className="h-3 w-3 text-amber-500" />
              ) : (
                <Clock3 className="h-3 w-3 text-muted-foreground" />
              )}
              {d.statusLabel}
            </div>
          </div>
          <div className="rounded-lg border border-border/50 bg-muted/50 px-2.5 py-2">
            <div className="text-muted-foreground">Depth</div>
            <div className="mt-1 font-medium">{d.depth}</div>
          </div>
          <div
            className={cn(
              "rounded-lg border px-2.5 py-2",
              d.threadHref
                ? "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300"
                : "border-border/50 bg-muted/50 text-muted-foreground"
            )}
            onClick={(event) => {
              event.stopPropagation();
              d.onOpenThread?.();
            }}
          >
            <div className="text-muted-foreground">Thread</div>
            <div className="mt-1 flex items-center gap-1 font-medium">
              {d.threadHref ? <ExternalLink className="h-3 w-3" /> : <Route className="h-3 w-3" />}
              {d.threadHref ? "open thread" : "no link"}
            </div>
          </div>
          <div className="rounded-lg border border-border/50 bg-muted/50 px-2.5 py-2 col-span-2">
            <div className="text-muted-foreground">Attempts</div>
            <div className="mt-1 font-medium">{d.attempts ?? 0}</div>
          </div>
        </div>
        {d.prState || d.mergeGateStatus ? (
          <div className="mt-3 flex flex-wrap gap-2 border-t border-border/50 pt-3">
            {d.prState ? (
              <Badge variant="outline">PR {humanizeToken(d.prState)}</Badge>
            ) : null}
            {d.mergeGateStatus ? (
              <Badge variant="outline">{humanizeToken(d.mergeGateStatus)}</Badge>
            ) : null}
          </div>
        ) : null}
      </div>
      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-background !bg-muted-foreground" />
    </div>
  );
});

const nodeTypes = {
  oats: OatsNode,
};

function OatsGraph({
  run,
  selectedTaskId,
  onSelectTask,
}: {
  run: OvernightOatsRunRecord;
  selectedTaskId?: string | null;
  onSelectTask: (taskId: string) => void;
}) {
  const router = useRouter();
  const { fitView } = useReactFlow();

  const graph = useMemo(() => {
    const tasksById = new Map(run.tasks.map((task) => [task.taskId, task]));
    const nodes: Node[] = run.dag.nodes.map((node: OrchestrationDagNode) => {
      const isStale = node.isStale ?? isStaleHeartbeat(node.lastHeartbeatAt, node.isActive);
      const task = tasksById.get(node.id);
      return {
        id: node.id,
        type: "oats",
        position: { x: 0, y: 0 },
        draggable: false,
        data: {
          label: node.label,
          description: node.description,
          role: node.role,
          agent: node.agent,
          status: node.status,
          statusLabel: deriveOatsNodeLabel(node, isStale),
          statusTone: deriveOatsNodeTone(node, isStale),
          isActive: node.isActive,
          isStale,
          timedOut: node.timedOut,
          exitCode: node.exitCode,
          depth: node.depth,
          attempts: node.attempts,
          selectable: node.kind === "task",
          isSelected: node.kind === "task" && node.id === selectedTaskId,
          threadHref: node.conversationPath ?? undefined,
          prState: task?.taskPr?.state,
          mergeGateStatus: task?.taskPr?.mergeGateStatus,
          onSelect: () => {
            if (node.kind === "task") {
              onSelectTask(node.id);
            }
          },
          onOpenThread: () => {
            if (node.conversationPath) {
              router.push(node.conversationPath);
            }
          },
        } satisfies OatsNodeData,
      };
    });
    const edges: Edge[] = run.dag.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      animated: edge.label === "dispatches",
      label: edge.label === "depends_on" ? undefined : edge.label,
      style: {
        strokeWidth: 2,
        strokeDasharray: edge.label === "dispatches" ? "6 3" : undefined,
      },
      className: edge.label === "dispatches"
        ? "!stroke-sky-500/50"
        : "!stroke-muted-foreground/50",
    }));

    return getLayoutedElements(nodes, edges, "TB", {
      nodeWidth: OATS_NODE_WIDTH,
      nodeHeight: OATS_NODE_LAYOUT_HEIGHT,
    });
  }, [onSelectTask, router, run.dag.edges, run.dag.nodes, run.tasks, selectedTaskId]);

  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges);

  useEffect(() => {
    setNodes(graph.nodes);
    setEdges(graph.edges);
  }, [graph.edges, graph.nodes, setEdges, setNodes]);

  useEffect(() => {
    requestAnimationFrame(() => fitView({ padding: 0.2, duration: 250 }));
  }, [fitView, run.lastUpdatedAt, run.recordPath]);

  return (
    <div className="overflow-hidden rounded-2xl border bg-background">
      <div className="border-b bg-muted/30 px-4 py-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-sm font-medium">Overnight Oats DAG</div>
            <div className="text-xs text-muted-foreground">
              Planner and task execution graph with dependency edges.
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="gap-1 border-sky-500/30 text-sky-600 dark:text-sky-400">
              <Network className="h-3 w-3" />
              depth {run.dag.stats.maxDepth}
            </Badge>
            <Badge variant="outline" className="gap-1 border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
              <GitBranch className="h-3 w-3" />
              breadth {run.dag.stats.maxBreadth}
            </Badge>
            <Badge variant="outline" className="gap-1 border-amber-500/30 text-amber-600 dark:text-amber-400">
              <Clock3 className="h-3 w-3" />
              {run.dag.stats.timedOutCount} timed out
            </Badge>
            <Badge variant="outline" className="gap-1 border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
              <Activity className="h-3 w-3" />
              {run.dag.stats.activeCount} active
            </Badge>
          </div>
        </div>
      </div>
      <div className="h-[680px] bg-gradient-to-b from-muted/30 to-background">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          minZoom={0.2}
          maxZoom={1.5}
          className="[&_.react-flow__edge-path]:!stroke-muted-foreground/40"
        >
          <Background className="!bg-transparent" color="hsl(var(--muted-foreground) / 0.15)" gap={18} size={1.2} />
          <MiniMap
            pannable
            zoomable
            className="!bg-muted/50 !border-border"
            nodeColor={(node) => (node.id === "planner" ? "hsl(199 89% 48%)" : "hsl(263 70% 50%)")}
            maskColor="hsl(var(--background) / 0.7)"
          />
          <Controls showInteractive={false} className="!bg-card !border-border !shadow-lg [&>button]:!bg-card [&>button]:!border-border [&>button]:!text-foreground [&>button:hover]:!bg-muted" />
          <Panel position="top-left">
            <div className="rounded-xl border bg-card/90 px-3 py-2 text-xs shadow-lg backdrop-blur">
              <div className="font-medium text-foreground">Traversal</div>
              <div className="text-muted-foreground">
                {run.dag.stats.totalNodes} nodes / {run.dag.stats.totalEdges} edges
              </div>
            </div>
          </Panel>
        </ReactFlow>
      </div>
    </div>
  );
}

export function OvernightOatsPanel() {
  const { data: runs, isLoading: oatsLoading, mutate } = useOvernightOatsRuns();
  const [search, setSearch] = useState("");
  const [selectedRecordPath, setSelectedRecordPath] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<
    "refresh" | "resume" | "pause" | "cancel" | "retry" | "reroute" | "insert" | null
  >(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const filteredRuns = useMemo(() => {
    return (runs ?? []).filter((run) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        run.runTitle.toLowerCase().includes(q) ||
        run.repoRoot.toLowerCase().includes(q) ||
        run.runSpecPath.toLowerCase().includes(q)
      );
    }).sort(
      (a, b) =>
        new Date(b.lastUpdatedAt).getTime() - new Date(a.lastUpdatedAt).getTime()
    );
  }, [runs, search]);

  const selectedRun = useMemo(() => {
    if (selectedRecordPath) {
      return (
        filteredRuns.find((run) => run.recordPath === selectedRecordPath) ??
        filteredRuns[0] ??
        null
      );
    }
    return filteredRuns[0] ?? null;
  }, [filteredRuns, selectedRecordPath]);

  const { data: selectedRuntime } = useSWR<MaterializedRuntimeRun>(
    selectedRun ? endpoints.orchestrationRuntime(selectedRun.runId) : null,
    (url: string) => requestJson(url, undefined, normalizeRuntimeMaterializedRun),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      refreshInterval: selectedRun?.isRunning ? 5_000 : 0,
    }
  );

  const selectedRunViewModel = useMemo(
    () =>
      selectedRun ? buildOatsViewModel(selectedRun, selectedTaskId, selectedRuntime) : null,
    [selectedRun, selectedTaskId, selectedRuntime]
  );

  const aggregate = useMemo(() => {
    const providerBreakdown = filteredRuns.reduce<Record<string, number>>(
      (acc, run) => {
        for (const [provider, count] of Object.entries(run.dag.stats.providerBreakdown)) {
          acc[provider] = (acc[provider] || 0) + count;
        }
        return acc;
      },
      {}
    );

    return {
      runs: filteredRuns.length,
      tasks: filteredRuns.reduce((sum, run) => sum + run.tasks.length, 0),
      taskPrs: filteredRuns.reduce(
        (sum, run) => sum + buildOatsViewModel(run).taskPrSummary.total,
        0
      ),
      mergedTaskPrs: filteredRuns.reduce(
        (sum, run) => sum + buildOatsViewModel(run).taskPrSummary.merged,
        0
      ),
      readyForFinalReview: filteredRuns.filter(
        (run) => run.stackStatus === "ready_for_final_review"
      ).length,
      timedOut: filteredRuns.reduce((sum, run) => sum + run.dag.stats.timedOutCount, 0),
      active: filteredRuns.reduce((sum, run) => sum + run.dag.stats.activeCount, 0),
      blockedOrConflicted: filteredRuns.filter(
        (run) =>
          run.stackStatus === "blocked" || run.stackStatus === "resolving_conflict"
      ).length,
      providerBreakdown,
    };
  }, [filteredRuns]);

  useEffect(() => {
    setActionError(null);
  }, [selectedRun?.runId]);

  async function triggerRunAction(action: "refresh" | "resume") {
    if (!selectedRun || pendingAction) {
      return;
    }

    setPendingAction(action);
    setActionError(null);
    try {
      const nextRun =
        action === "refresh"
          ? await refreshOvernightOatsRun(selectedRun.runId)
          : await resumeOvernightOatsRun(selectedRun.runId);
      await mutate(replaceRunRecord(runs, nextRun), { revalidate: false });
      setSelectedRecordPath(nextRun.recordPath);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Run action failed.");
    } finally {
      setPendingAction(null);
    }
  }

  async function triggerPauseRun() {
    if (!selectedRun || pendingAction) {
      return;
    }

    setPendingAction("pause");
    setActionError(null);
    try {
      const nextRun = await pauseOvernightOatsRun(selectedRun.runId);
      await mutate(replaceRunRecord(runs, nextRun), { revalidate: false });
      setSelectedRecordPath(nextRun.recordPath);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Pause action failed.");
    } finally {
      setPendingAction(null);
    }
  }

  async function triggerTaskAction(action: "cancel" | "retry" | "reroute") {
    if (!selectedRun || !selectedTaskId || pendingAction) {
      return;
    }

    setPendingAction(action);
    setActionError(null);
    try {
      let nextRun: OvernightOatsRunRecord;
      if (action === "cancel") {
        nextRun = await cancelOvernightOatsTask(selectedRun.runId, selectedTaskId);
      } else if (action === "retry") {
        nextRun = await forceRetryOvernightOatsTask(selectedRun.runId, selectedTaskId);
      } else {
        const providerInput = window.prompt("Re-route provider (claude or codex)", "codex");
        if (providerInput !== "claude" && providerInput !== "codex") {
          setPendingAction(null);
          return;
        }
        const modelInput = window.prompt("Model override", providerInput === "codex" ? "o3-pro" : "claude-sonnet-4-6");
        nextRun = await rerouteOvernightOatsTask(selectedRun.runId, selectedTaskId, {
          provider: providerInput,
          model: modelInput || undefined,
        });
      }
      await mutate(replaceRunRecord(runs, nextRun), { revalidate: false });
      setSelectedRecordPath(nextRun.recordPath);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Task action failed.");
    } finally {
      setPendingAction(null);
    }
  }

  async function triggerInsertTask() {
    if (!selectedRun || pendingAction) {
      return;
    }

    const title = window.prompt("New task title", "Operator-added task");
    if (!title) {
      return;
    }

    setPendingAction("insert");
    setActionError(null);
    try {
      const nextRun = await insertOvernightOatsTask(selectedRun.runId, {
        title,
        kind: "implementation",
        dependencies: selectedTaskId
          ? [{ taskId: selectedTaskId, predicate: "code_ready" }]
          : [],
        agent: "claude",
        model: "claude-sonnet-4-6",
      });
      await mutate(replaceRunRecord(runs, nextRun), { revalidate: false });
      setSelectedRecordPath(nextRun.recordPath);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Insert task failed.");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <Input
          placeholder="Search Oats runs, repos..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="max-w-md"
        />
        <div className="text-sm text-muted-foreground">
          {filteredRuns.length} Oats run{filteredRuns.length === 1 ? "" : "s"} shown
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-sky-500/20 bg-sky-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Runs
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <Layers2 className="h-5 w-5 text-sky-500" />
              {aggregate.runs}
            </div>
          </CardContent>
        </Card>
        <Card className="border-violet-500/20 bg-violet-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Tasks / PRs
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <PlaySquare className="h-5 w-5 text-violet-500" />
              {aggregate.tasks}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              {aggregate.taskPrs} task PRs, {aggregate.mergedTaskPrs} merged
            </div>
          </CardContent>
        </Card>
        <Card className="border-emerald-500/20 bg-emerald-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Final Review Ready
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <ShieldAlert className="h-5 w-5 text-emerald-500" />
              {aggregate.readyForFinalReview}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              {aggregate.blockedOrConflicted} blocked or resolving conflict
            </div>
          </CardContent>
        </Card>
        <Card className="border-amber-500/20 bg-amber-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Provider mix
            </div>
            <div className="mt-2 flex items-center gap-2 flex-wrap text-sm font-medium">
              {Object.entries(aggregate.providerBreakdown).map(([provider, count]) => (
                <Badge key={provider} variant="outline">
                  {provider} {count}
                </Badge>
              ))}
              {aggregate.timedOut > 0 && (
                <Badge variant="outline" className="gap-1">
                  <TimerOff className="h-3.5 w-3.5" />
                  {aggregate.timedOut} timed out
                </Badge>
              )}
              {aggregate.active > 0 && (
                <Badge variant="outline" className="gap-1 border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-400">
                  <Activity className="h-3.5 w-3.5" />
                  {aggregate.active} active
                </Badge>
              )}
              {aggregate.blockedOrConflicted > 0 && (
                <Badge variant="outline" className="gap-1 border-rose-300 text-rose-700 dark:border-rose-800 dark:text-rose-300">
                  <CircleAlert className="h-3.5 w-3.5" />
                  {aggregate.blockedOrConflicted} blocked
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-dashed">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div>
            <div className="text-sm font-medium">Operator surfaces</div>
            <div className="text-sm text-muted-foreground">
              Jump between run state, workers, credentials, and dispatch monitoring.
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline" size="sm">
              <a href="#worker-dashboard">Worker Dashboard</a>
            </Button>
            <Button asChild variant="outline" size="sm">
              <a href="#auth-management">Auth Management</a>
            </Button>
            <Button asChild variant="outline" size="sm">
              <a href="#queue-monitor">Queue Monitor</a>
            </Button>
          </div>
        </CardContent>
      </Card>

      {oatsLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
      ) : filteredRuns.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">
          No authoritative OATS runs found in the backend orchestration store.
        </p>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="space-y-3">
            {filteredRuns.map((run) => {
              const runViewModel = buildOatsViewModel(run);
              const stackLabel = humanizeToken(run.stackStatus ?? "building");
              const isSelected = selectedRun?.recordPath === run.recordPath;
              return (
                <Card
                  key={run.recordPath}
                  className={`cursor-pointer transition-colors ${
                    isSelected ? "border-primary" : "hover:bg-accent/40"
                  }`}
                  onClick={() => {
                    setSelectedRecordPath(run.recordPath);
                    setSelectedTaskId(null);
                  }}
                >
                  <CardContent className="p-4">
                    <div className="space-y-2">
                      <div className="line-clamp-2 text-sm font-medium">
                        {run.runTitle}
                      </div>
                      <div className="text-xs text-muted-foreground">{run.repoRoot}</div>
                      <div className="text-xs text-muted-foreground">
                        feature {run.featureBranch?.name ?? run.integrationBranch}
                      </div>
                      <div className="flex items-center gap-2 flex-wrap text-xs">
                        <Badge variant="secondary">Oats run</Badge>
                        <Badge variant="outline" className="gap-1">
                          <PlaySquare className="h-3 w-3" />
                          {run.tasks.length} tasks
                        </Badge>
                        <Badge variant="outline">{run.status}</Badge>
                        <Badge variant="outline">{stackLabel}</Badge>
                        {runViewModel.taskPrSummary.total > 0 ? (
                          <Badge variant="outline">
                            {runViewModel.taskPrSummary.merged}/{runViewModel.taskPrSummary.total} merged
                          </Badge>
                        ) : null}
                        {run.stackStatus === "ready_for_final_review" ? (
                          <Badge variant="outline" className="border-amber-400/50 text-amber-700 dark:text-amber-300">
                            awaiting final review
                          </Badge>
                        ) : null}
                        {run.stackStatus === "blocked" || run.stackStatus === "resolving_conflict" ? (
                          <Badge variant="outline" className="border-rose-400/50 text-rose-700 dark:text-rose-300">
                            {run.stackStatus === "resolving_conflict" ? "conflict" : "blocked"}
                          </Badge>
                        ) : null}
                        {run.isRunning && (
                          <Badge variant="outline" className="gap-2 border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-400">
                            <span className="relative flex h-2.5 w-2.5">
                              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                            </span>
                            running
                          </Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        updated{" "}
                        {formatDistanceToNow(new Date(run.lastUpdatedAt), {
                          addSuffix: true,
                        })}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        created{" "}
                        {formatDistanceToNow(new Date(run.createdAt), {
                          addSuffix: true,
                        })}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {selectedRun && (
            <div className="space-y-4">
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="space-y-2">
                      <div className="text-lg font-semibold">{selectedRun.runTitle}</div>
                      <div className="text-sm text-muted-foreground">
                        {selectedRun.repoRoot}
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="secondary">Oats run</Badge>
                        {selectedRun.mode ? <Badge variant="outline">{selectedRun.mode}</Badge> : null}
                        {selectedRun.featureBranch?.name ?? selectedRun.integrationBranch ? (
                          <Badge variant="secondary">
                            {selectedRun.featureBranch?.name ?? selectedRun.integrationBranch}
                          </Badge>
                        ) : null}
                        <Badge variant="outline">{selectedRun.status}</Badge>
                        {selectedRun.stackStatus ? (
                          <Badge variant="outline">{humanizeToken(selectedRun.stackStatus)}</Badge>
                        ) : null}
                        {selectedRunViewModel && selectedRunViewModel.taskPrSummary.total > 0 ? (
                          <Badge variant="outline">
                            {selectedRunViewModel.taskPrSummary.merged}/
                            {selectedRunViewModel.taskPrSummary.total} task PRs merged
                          </Badge>
                        ) : null}
                        {selectedRun.runSpecPath ? (
                          <Badge variant="outline">
                            spec: {selectedRun.runSpecPath.split("/").pop()}
                          </Badge>
                        ) : null}
                        {selectedRun.isRunning && (
                          <Badge variant="outline" className="gap-2 border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-400">
                            <span className="relative flex h-2.5 w-2.5">
                              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                            </span>
                            running
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="space-y-3 text-sm text-muted-foreground text-right">
                      <div>
                        <div>Created {new Date(selectedRun.createdAt).toLocaleString()}</div>
                        <div>Updated {new Date(selectedRun.lastUpdatedAt).toLocaleString()}</div>
                        {selectedRun.heartbeatAt && (
                          <div>Heartbeat {new Date(selectedRun.heartbeatAt).toLocaleString()}</div>
                        )}
                        <div className="mt-1 flex items-center justify-end gap-2">
                          <Bot className="h-4 w-4" />
                          {selectedRun.dag.stats.totalNodes} nodes
                        </div>
                      </div>
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={pendingAction !== null}
                          onClick={() => void triggerRunAction("refresh")}
                        >
                          {pendingAction === "refresh" ? "Refreshing..." : "Refresh PR stack"}
                        </Button>
                        <Button
                          size="sm"
                          disabled={pendingAction !== null}
                          onClick={() => void triggerRunAction("resume")}
                        >
                          {pendingAction === "resume" ? "Resuming..." : "Resume run"}
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={pendingAction !== null}
                          onClick={() => void triggerPauseRun()}
                        >
                          {pendingAction === "pause" ? "Pausing..." : "Pause run"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={pendingAction !== null}
                          onClick={() => void triggerInsertTask()}
                        >
                          {pendingAction === "insert" ? "Inserting..." : "Insert task"}
                        </Button>
                      </div>
                      {selectedTaskId ? (
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={pendingAction !== null}
                            onClick={() => void triggerTaskAction("cancel")}
                          >
                            {pendingAction === "cancel" ? "Cancelling..." : `Cancel ${selectedTaskId}`}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={pendingAction !== null}
                            onClick={() => void triggerTaskAction("retry")}
                          >
                            {pendingAction === "retry" ? "Retrying..." : `Force retry ${selectedTaskId}`}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={pendingAction !== null}
                            onClick={() => void triggerTaskAction("reroute")}
                          >
                            {pendingAction === "reroute" ? "Re-routing..." : `Re-route ${selectedTaskId}`}
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                  {actionError ? (
                    <div className="mt-4 rounded-xl border border-rose-400/40 bg-rose-500/5 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">
                      {actionError}
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              {selectedRunViewModel ? (
                <OatsPrStack
                  run={selectedRun}
                  viewModel={selectedRunViewModel}
                  onSelectTask={setSelectedTaskId}
                />
              ) : null}

              <ReactFlowProvider>
                <OatsGraph
                  run={selectedRun}
                  selectedTaskId={selectedRunViewModel?.selectedTaskId}
                  onSelectTask={setSelectedTaskId}
                />
              </ReactFlowProvider>

              {selectedRunViewModel ? (
                <Card>
                  <CardContent className="space-y-4 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium">Runtime truth</div>
                        <div className="text-sm text-muted-foreground">
                          Materialized attempts, dispatches, and graph mutations for the live run.
                        </div>
                      </div>
                      <Badge variant="outline">
                        {selectedRunViewModel.graphMutations.length} mutation
                        {selectedRunViewModel.graphMutations.length === 1 ? "" : "s"}
                      </Badge>
                    </div>

                    {selectedRunViewModel.selectedTaskId ? (
                      <div className="grid gap-4 lg:grid-cols-2">
                        <div className="space-y-2">
                          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Selected task attempts
                          </div>
                          {selectedRunViewModel.selectedTaskAttempts.length > 0 ? (
                            selectedRunViewModel.selectedTaskAttempts.map((attempt) => (
                              <div
                                key={attempt.attemptId ?? `${attempt.taskId}-${attempt.status}`}
                                className="rounded-xl border bg-muted/30 p-3 text-sm"
                              >
                                <div className="flex flex-wrap items-center gap-2">
                                  <Badge variant="secondary">{attempt.status}</Badge>
                                  {attempt.attemptId ? (
                                    <Badge variant="outline">{attempt.attemptId}</Badge>
                                  ) : null}
                                  {attempt.workerId ? (
                                    <Badge variant="outline">worker {attempt.workerId}</Badge>
                                  ) : null}
                                  {attempt.providerSessionId ? (
                                    <Badge variant="outline">session {attempt.providerSessionId}</Badge>
                                  ) : null}
                                  {attempt.sessionReused ? (
                                    <Badge variant="outline">session reused</Badge>
                                  ) : null}
                                  {attempt.sessionStatusAfterTask ? (
                                    <Badge variant="outline">{attempt.sessionStatusAfterTask}</Badge>
                                  ) : null}
                                </div>
                                <div className="mt-2 text-muted-foreground">
                                  {attempt.durationSeconds != null
                                    ? `${attempt.durationSeconds}s`
                                    : "duration unavailable"}
                                  {attempt.branchName ? ` · ${attempt.branchName}` : ""}
                                  {attempt.commitSha ? ` · ${attempt.commitSha}` : ""}
                                </div>
                                {attempt.errorSummary ? (
                                  <div className="mt-2 text-rose-700 dark:text-rose-300">
                                    {attempt.errorSummary}
                                  </div>
                                ) : null}
                              </div>
                            ))
                          ) : (
                            <div className="rounded-xl border border-dashed p-3 text-sm text-muted-foreground">
                              No materialized attempts for {selectedRunViewModel.selectedTaskId} yet.
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Selected task dispatch
                          </div>
                          {selectedRunViewModel.selectedTaskDispatchEvents.length > 0 ? (
                            selectedRunViewModel.selectedTaskDispatchEvents.map((event) => (
                              <div
                                key={`${event.taskId}-${event.dispatchedAt}-${event.workerId}`}
                                className="rounded-xl border bg-muted/30 p-3 text-sm"
                              >
                                <div className="flex flex-wrap items-center gap-2">
                                  <Badge variant="secondary">{event.provider}</Badge>
                                  <Badge variant="outline">{event.model}</Badge>
                                  <Badge variant="outline">worker {event.workerId}</Badge>
                                </div>
                                <div className="mt-2 text-muted-foreground">
                                  dispatched {new Date(event.dispatchedAt).toLocaleString()}
                                </div>
                              </div>
                            ))
                          ) : (
                            <div className="rounded-xl border border-dashed p-3 text-sm text-muted-foreground">
                              No dispatch history for {selectedRunViewModel.selectedTaskId} yet.
                            </div>
                          )}
                        </div>
                      </div>
                    ) : null}

                    <div className="space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Operator actions
                      </div>
                      {selectedRunViewModel.operatorActions.length > 0 ? (
                        selectedRunViewModel.operatorActions.map((action) => (
                          <div
                            key={`${action.action}-${action.createdAt}-${action.targetTaskId ?? "run"}`}
                            className="rounded-xl border bg-muted/30 p-3 text-sm"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="secondary">{action.action}</Badge>
                              <Badge variant="outline">{action.actor}</Badge>
                              {action.targetTaskId ? (
                                <Badge variant="outline">{action.targetTaskId}</Badge>
                              ) : null}
                            </div>
                            <div className="mt-2 text-muted-foreground">
                              {action.createdAt
                                ? new Date(action.createdAt).toLocaleString()
                                : "timestamp unavailable"}
                            </div>
                            {Object.keys(action.details).length > 0 ? (
                              <div className="mt-2 text-muted-foreground">
                                {Object.entries(action.details)
                                  .map(([key, value]) => `${key}: ${String(value)}`)
                                  .join(" · ")}
                              </div>
                            ) : null}
                          </div>
                        ))
                      ) : (
                        <div className="rounded-xl border border-dashed p-3 text-sm text-muted-foreground">
                          No operator actions have been materialized for this run yet.
                        </div>
                      )}
                    </div>

                    <div className="space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Graph mutations
                      </div>
                      {selectedRunViewModel.graphMutations.length > 0 ? (
                        selectedRunViewModel.graphMutations.map((mutation) => (
                          <div
                            key={`${mutation.mutationId}-${mutation.timestamp}`}
                            className="rounded-xl border bg-muted/30 p-3 text-sm"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="secondary">{mutation.kind}</Badge>
                              <Badge variant="outline">{mutation.source}</Badge>
                              <Badge variant="outline">{mutation.discoveredBy}</Badge>
                            </div>
                            <div className="mt-2 text-muted-foreground">
                              {mutation.timestamp
                                ? new Date(mutation.timestamp).toLocaleString()
                                : "timestamp unavailable"}
                              {mutation.nodesAdded.length > 0
                                ? ` · nodes ${mutation.nodesAdded.join(", ")}`
                                : ""}
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="rounded-xl border border-dashed p-3 text-sm text-muted-foreground">
                          No materialized graph mutations yet.
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ) : null}

              <Card>
                <CardContent className="p-4">
                  <div className="mb-3 text-sm font-medium">Session links</div>
                  <div className="space-y-2 text-sm">
                    {selectedRun.planner?.conversationPath && (
                      <a
                        href={selectedRun.planner.conversationPath}
                        className="flex items-center gap-2 text-primary hover:underline"
                      >
                        <Route className="h-4 w-4" />
                        Planner {selectedRun.planner.agent} thread
                      </a>
                    )}
                    {selectedRun.tasks.map((task) => (
                      <div key={task.taskId}>
                        {task.invocation?.conversationPath ? (
                          <a
                            href={task.invocation.conversationPath}
                            className="flex items-center gap-2 text-primary hover:underline"
                          >
                            <Route className="h-4 w-4" />
                            {task.taskId} {task.invocation.agent} thread
                          </a>
                        ) : (
                          <div className="text-muted-foreground">
                            {task.taskId} has no invocation session link
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      <OperatorBootstrapPanelContainer />
      <WorkerDashboardPanel />
      <AuthManagementPanel />
      <QueueMonitorPanel />
    </div>
  );
}
