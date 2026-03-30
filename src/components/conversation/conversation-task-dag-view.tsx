"use client";

import { memo, useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";
import {
  CheckCircle2,
  Circle,
  CircleDashed,
  GitBranch,
  ListTodo,
  Shuffle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { getLayoutedElements } from "@/lib/conversation-dag-layout";
import { cn } from "@/lib/utils";
import type {
  ConversationTaskDag,
  ConversationTaskDagNode as ConversationTaskNodeModel,
} from "@/lib/conversation-task-dag";

interface TaskNodeData {
  title: string;
  taskId: string;
  status?: string;
  dependencyCount: number;
}

const nodeTypes = {
  task: memo(function TaskNode({ data }: NodeProps) {
    const task = data as unknown as TaskNodeData;
    const statusLabel = formatStatus(task.status);
    const tone = statusTone(task.status);

    return (
      <div
        className={cn(
          "nodrag w-[280px] rounded-2xl border-2 bg-card text-card-foreground shadow-lg",
          tone === "success" && "border-emerald-500/45 ring-1 ring-emerald-500/15",
          tone === "warning" && "border-amber-500/45 ring-1 ring-amber-500/15",
          tone === "running" && "border-sky-500/45 ring-1 ring-sky-500/15",
          tone === "pending" && "border-violet-500/40 ring-1 ring-violet-500/15",
          tone === "unknown" && "border-border"
        )}
      >
        <Handle
          type="target"
          position={Position.Top}
          className="!bg-muted-foreground !border-background !w-2.5 !h-2.5"
        />

        <div className="border-b px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="line-clamp-2 text-sm font-semibold">{task.title}</div>
              <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                {task.taskId}
              </div>
            </div>
            <Badge variant="outline" className="shrink-0 bg-muted/40">
              {statusIcon(task.status)}
              {statusLabel}
            </Badge>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 px-4 py-3 text-xs">
          <div className="rounded-lg border bg-muted/40 px-2.5 py-2 text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <GitBranch className="h-3 w-3 text-emerald-500" />
              <span className="font-medium text-foreground/80">
                {task.dependencyCount}
              </span>
              deps
            </div>
          </div>
          <div className="rounded-lg border bg-muted/40 px-2.5 py-2 text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <ListTodo className="h-3 w-3 text-sky-500" />
              node
            </div>
          </div>
        </div>

        <Handle
          type="source"
          position={Position.Bottom}
          className="!bg-muted-foreground !border-background !w-2.5 !h-2.5"
        />
      </div>
    );
  }),
};

function statusIcon(status?: string) {
  const tone = statusTone(status);
  if (tone === "success") return <CheckCircle2 className="h-3 w-3" />;
  if (tone === "running") return <CircleDashed className="h-3 w-3" />;
  return <Circle className="h-3 w-3" />;
}

function statusTone(status?: string): "success" | "running" | "warning" | "pending" | "unknown" {
  if (!status) return "unknown";
  if (["completed", "done", "succeeded", "success"].includes(status)) return "success";
  if (["in_progress", "running", "active"].includes(status)) return "running";
  if (["blocked", "failed", "error"].includes(status)) return "warning";
  if (["pending", "todo", "not_started"].includes(status)) return "pending";
  return "unknown";
}

function formatStatus(status?: string): string {
  if (!status) return "unknown";
  return status.replace(/_/g, " ");
}

function sourceLabel(source: ConversationTaskDag["source"]): string {
  if (source === "codex-plan") return "latest Codex plan";
  if (source === "tasks") return "conversation tasks";
  return "no task source";
}

function TaskDagCanvas({ dag }: { dag: ConversationTaskDag }) {
  const { fitView } = useReactFlow();

  const graph = useMemo(() => {
    const nodes: Node[] = dag.nodes.map((node: ConversationTaskNodeModel) => ({
      id: node.id,
      type: "task",
      position: { x: 0, y: 0 },
      draggable: false,
      data: {
        title: node.title,
        taskId: node.taskId,
        status: node.status,
        dependencyCount: node.dependsOn.length,
      } satisfies TaskNodeData,
    }));
    const edges: Edge[] = dag.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      animated: edge.inferred,
      style: {
        strokeWidth: 2,
      },
      className: edge.inferred ? "!stroke-sky-500/45" : "!stroke-violet-500/45",
    }));

    return getLayoutedElements(nodes, edges, "TB", {
      nodeWidth: 280,
      nodeHeight: 138,
    });
  }, [dag.edges, dag.nodes]);

  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges);

  useEffect(() => {
    setNodes(graph.nodes);
    setEdges(graph.edges);
    requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 250 });
    });
  }, [fitView, graph.edges, graph.nodes, setEdges, setNodes]);

  return (
    <div className="overflow-hidden rounded-2xl border bg-background">
      <div className="border-b bg-muted/30 px-4 py-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-sm font-medium">Task DAG</div>
            <div className="text-xs text-muted-foreground">
              Parsed from {sourceLabel(dag.source)}.
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="gap-1 border-sky-500/30 text-sky-600 dark:text-sky-400">
              <ListTodo className="h-3 w-3" />
              {dag.stats.totalNodes} tasks
            </Badge>
            <Badge variant="outline" className="gap-1 border-violet-500/30 text-violet-600 dark:text-violet-400">
              <Shuffle className="h-3 w-3" />
              {dag.stats.totalEdges} edges
            </Badge>
            <Badge variant="outline" className="gap-1 border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-3 w-3" />
              {dag.stats.completedNodes} completed
            </Badge>
          </div>
        </div>
      </div>

      <div className="h-[560px] bg-gradient-to-b from-muted/30 to-background">
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
          <Controls showInteractive={false} className="!bg-card !border-border !shadow-lg [&>button]:!bg-card [&>button]:!border-border [&>button]:!text-foreground [&>button:hover]:!bg-muted" />
          <Panel position="top-left">
            <div className="rounded-xl border bg-card/90 px-3 py-2 text-xs shadow-lg backdrop-blur">
              <div className="font-medium text-foreground">Source</div>
              <div className="text-muted-foreground">{sourceLabel(dag.source)}</div>
            </div>
          </Panel>
        </ReactFlow>
      </div>
    </div>
  );
}

export function ConversationTaskDagView({ dag }: { dag: ConversationTaskDag }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <Card className="border-sky-500/20 bg-sky-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Total tasks
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <ListTodo className="h-5 w-5 text-sky-500" />
              {dag.stats.totalNodes}
            </div>
          </CardContent>
        </Card>
        <Card className="border-violet-500/20 bg-violet-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Dependencies
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <GitBranch className="h-5 w-5 text-violet-500" />
              {dag.stats.totalEdges}
            </div>
          </CardContent>
        </Card>
        <Card className="border-emerald-500/20 bg-emerald-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Completed
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
              {dag.stats.completedNodes}
            </div>
          </CardContent>
        </Card>
      </div>

      <ReactFlowProvider>
        <TaskDagCanvas dag={dag} />
      </ReactFlowProvider>

      <Card>
        <CardContent className="p-4 space-y-3">
          <div>
            <div className="text-sm font-medium">Parsed tasks</div>
            <div className="text-xs text-muted-foreground">
              Ordered task summary from {sourceLabel(dag.source)}.
            </div>
          </div>
          <div className="space-y-2">
            {dag.nodes.map((node) => (
              <div
                key={node.id}
                className="flex items-start justify-between gap-3 rounded-xl border bg-muted/20 px-3 py-3"
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium">{node.title}</div>
                  <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                    {node.taskId}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant="outline" className="bg-muted/40">
                    {node.dependsOn.length} deps
                  </Badge>
                  <Badge variant="outline" className="bg-muted/40">
                    {formatStatus(node.status)}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
