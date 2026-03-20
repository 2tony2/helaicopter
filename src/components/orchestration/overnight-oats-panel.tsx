"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
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
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { getLayoutedElements } from "@/lib/conversation-dag-layout";
import { useOvernightOatsRuns } from "@/hooks/use-conversations";
import type {
  OrchestrationDagNode,
  OrchestrationStatusTone,
  OvernightOatsRunRecord,
} from "@/lib/types";
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
  clickable: boolean;
  onClick: () => void;
}

const OATS_NODE_WIDTH = 280;
const OATS_NODE_LAYOUT_HEIGHT = 212;
const OATS_STALE_AFTER_MS = 300_000;

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
        "nodrag flex w-[280px] min-h-[212px] flex-col overflow-hidden rounded-2xl border-2 bg-card text-card-foreground shadow-lg transition-all hover:shadow-xl hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        isPlanner ? "bg-slate-50/70 dark:bg-slate-950/20" : "",
        statusToneClass
      )}
      onClick={d.onClick}
      role={d.clickable ? "button" : undefined}
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          d.onClick();
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
              d.clickable
                ? "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300"
                : "border-border/50 bg-muted/50 text-muted-foreground"
            )}
          >
            <div className="text-muted-foreground">Thread</div>
            <div className="mt-1 flex items-center gap-1 font-medium">
              {d.clickable ? <ExternalLink className="h-3 w-3" /> : <Route className="h-3 w-3" />}
              {d.clickable ? "open thread" : "no link"}
            </div>
          </div>
          <div className="rounded-lg border border-border/50 bg-muted/50 px-2.5 py-2 col-span-2">
            <div className="text-muted-foreground">Attempts</div>
            <div className="mt-1 font-medium">{d.attempts ?? 0}</div>
          </div>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-background !bg-muted-foreground" />
    </div>
  );
});

const nodeTypes = {
  oats: OatsNode,
};

function OatsGraph({ run }: { run: OvernightOatsRunRecord }) {
  const router = useRouter();
  const { fitView } = useReactFlow();

  const graph = useMemo(() => {
    const nodes: Node[] = run.dag.nodes.map((node: OrchestrationDagNode) => {
      const isStale = node.isStale ?? isStaleHeartbeat(node.lastHeartbeatAt, node.isActive);
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
          clickable: Boolean(node.conversationPath),
          onClick: () => {
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
  }, [router, run.dag.edges, run.dag.nodes]);

  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges);

  useEffect(() => {
    setNodes(graph.nodes);
    setEdges(graph.edges);
    requestAnimationFrame(() => fitView({ padding: 0.2, duration: 250 }));
  }, [fitView, graph.edges, graph.nodes, setEdges, setNodes]);

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
  const { data: runs, isLoading: oatsLoading } = useOvernightOatsRuns();
  const [search, setSearch] = useState("");
  const [selectedRecordPath, setSelectedRecordPath] = useState<string | null>(null);

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
      deepest: filteredRuns.reduce((max, run) => Math.max(max, run.dag.stats.maxDepth), 0),
      timedOut: filteredRuns.reduce((sum, run) => sum + run.dag.stats.timedOutCount, 0),
      active: filteredRuns.reduce((sum, run) => sum + run.dag.stats.activeCount, 0),
      providerBreakdown,
    };
  }, [filteredRuns]);

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
              Tasks
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <PlaySquare className="h-5 w-5 text-violet-500" />
              {aggregate.tasks}
            </div>
          </CardContent>
        </Card>
        <Card className="border-emerald-500/20 bg-emerald-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Deepest run
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <Network className="h-5 w-5 text-emerald-500" />
              {aggregate.deepest}
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
            </div>
          </CardContent>
        </Card>
      </div>

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
              const isSelected = selectedRun?.recordPath === run.recordPath;
              return (
                <Card
                  key={run.recordPath}
                  className={`cursor-pointer transition-colors ${
                    isSelected ? "border-primary" : "hover:bg-accent/40"
                  }`}
                  onClick={() => setSelectedRecordPath(run.recordPath)}
                >
                  <CardContent className="p-4">
                    <div className="space-y-2">
                      <div className="line-clamp-2 text-sm font-medium">
                        {run.runTitle}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {run.repoRoot}
                      </div>
                      <div className="flex items-center gap-2 flex-wrap text-xs">
                        <Badge variant="secondary">Oats run</Badge>
                        <Badge variant="outline" className="gap-1">
                          <PlaySquare className="h-3 w-3" />
                          {run.tasks.length} tasks
                        </Badge>
                        <Badge variant="outline" className="gap-1">
                          <Network className="h-3 w-3" />
                          depth {run.dag.stats.maxDepth}
                        </Badge>
                        <Badge variant="outline" className="gap-1">
                          <GitBranch className="h-3 w-3" />
                          breadth {run.dag.stats.maxBreadth}
                        </Badge>
                        <Badge variant="outline">{run.status}</Badge>
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
                        {selectedRun.integrationBranch ? (
                          <Badge variant="secondary">{selectedRun.integrationBranch}</Badge>
                        ) : null}
                        <Badge variant="outline">{selectedRun.status}</Badge>
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
                    <div className="text-sm text-muted-foreground text-right">
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
                  </div>
                </CardContent>
              </Card>

              <ReactFlowProvider>
                <OatsGraph run={selectedRun} />
              </ReactFlowProvider>

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
    </div>
  );
}
