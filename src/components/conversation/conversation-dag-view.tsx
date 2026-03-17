"use client";

import { useEffect, useMemo } from "react";
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
} from "@xyflow/react";
import { Bot, GitBranch, Layers2, MessageSquare, Network } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { getLayoutedElements } from "@/lib/conversation-dag-layout";
import type { ConversationDag } from "@/lib/types";
import {
  ConversationDagNode,
  type ConversationDagNodeData,
} from "./conversation-dag-node";

const nodeTypes = {
  conversation: ConversationDagNode,
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function DagCanvas({ dag }: { dag: ConversationDag }) {
  const router = useRouter();
  const { fitView } = useReactFlow();

  const graph = useMemo(() => {
    const nodes: Node[] = dag.nodes.map((node) => ({
      id: node.id,
      type: "conversation",
      position: { x: 0, y: 0 },
      draggable: false,
      data: {
        label: node.label,
        description: node.description,
        nickname: node.nickname,
        subagentType: node.subagentType,
        threadType: node.threadType,
        hasTranscript: node.hasTranscript,
        model: node.model,
        messageCount: node.messageCount,
        totalTokens: formatTokens(node.totalTokens),
        depth: node.depth,
        isRoot: node.isRoot,
        onClick: () => router.push(node.path),
      } satisfies ConversationDagNodeData,
    }));
    const edges: Edge[] = dag.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      animated: true,
      style: {
        strokeWidth: 2,
      },
      className: "!stroke-muted-foreground/50",
    }));

    return getLayoutedElements(nodes, edges, "TB");
  }, [dag, router]);

  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges);

  useEffect(() => {
    setNodes(graph.nodes);
    setEdges(graph.edges);
    requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 300 });
    });
  }, [fitView, graph.edges, graph.nodes, setEdges, setNodes]);

  return (
    <div className="overflow-hidden rounded-2xl border bg-background">
      <div className="border-b bg-muted/30 px-4 py-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-sm font-medium">Sub-agent DAG</div>
            <div className="text-xs text-muted-foreground">
              Click any node to open that thread.
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="gap-1 border-violet-500/30 text-violet-600 dark:text-violet-400">
              <Bot className="h-3 w-3" />
              {dag.stats.totalSubagentNodes} sub-agents
            </Badge>
            <Badge variant="outline" className="gap-1 border-sky-500/30 text-sky-600 dark:text-sky-400">
              <Network className="h-3 w-3" />
              depth {dag.stats.maxDepth}
            </Badge>
            <Badge variant="outline" className="gap-1 border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
              <GitBranch className="h-3 w-3" />
              breadth {dag.stats.maxBreadth}
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
            nodeColor={(node) =>
              node.id === dag.rootSessionId ? "hsl(199 89% 48%)" : "hsl(263 70% 50%)"
            }
            maskColor="hsl(var(--background) / 0.7)"
          />
          <Controls showInteractive={false} className="!bg-card !border-border !shadow-lg [&>button]:!bg-card [&>button]:!border-border [&>button]:!text-foreground [&>button:hover]:!bg-muted" />
          <Panel position="top-left">
            <div className="rounded-xl border bg-card/90 px-3 py-2 text-xs shadow-lg backdrop-blur">
              <div className="font-medium text-foreground">Traversal</div>
              <div className="text-muted-foreground">
                {dag.stats.totalNodes} nodes / {dag.stats.totalEdges} edges
              </div>
            </div>
          </Panel>
        </ReactFlow>
      </div>
    </div>
  );
}

export function ConversationDagView({ dag }: { dag: ConversationDag }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-sky-500/20 bg-sky-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Total nodes
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <Layers2 className="h-5 w-5 text-sky-500" />
              {dag.stats.totalNodes}
            </div>
          </CardContent>
        </Card>
        <Card className="border-violet-500/20 bg-violet-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Max depth
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <Network className="h-5 w-5 text-violet-500" />
              {dag.stats.maxDepth}
            </div>
          </CardContent>
        </Card>
        <Card className="border-emerald-500/20 bg-emerald-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Max breadth
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <GitBranch className="h-5 w-5 text-emerald-500" />
              {dag.stats.maxBreadth}
            </div>
          </CardContent>
        </Card>
        <Card className="border-amber-500/20 bg-amber-500/5">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Total messages
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <MessageSquare className="h-5 w-5 text-amber-500" />
              {dag.stats.totalMessages}
            </div>
          </CardContent>
        </Card>
      </div>

      <ReactFlowProvider>
        <DagCanvas dag={dag} />
      </ReactFlowProvider>
    </div>
  );
}
