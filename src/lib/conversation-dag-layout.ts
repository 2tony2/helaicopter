import dagre from "@dagrejs/dagre";
import { Position, type Edge, type Node } from "@xyflow/react";

const NODE_WIDTH = 260;
const NODE_HEIGHT = 128;

export function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction: "TB" | "LR" = "TB"
): { nodes: Node[]; edges: Edge[] } {
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: direction,
    nodesep: direction === "LR" ? 48 : 28,
    ranksep: direction === "LR" ? 92 : 96,
    marginx: 24,
    marginy: 24,
  });

  nodes.forEach((node) => {
    graph.setNode(node.id, {
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    });
  });

  edges.forEach((edge) => {
    graph.setEdge(edge.source, edge.target);
  });

  dagre.layout(graph);

  return {
    nodes: nodes.map((node) => {
      const position = graph.node(node.id);
      return {
        ...node,
        targetPosition: direction === "LR" ? Position.Left : Position.Top,
        sourcePosition: direction === "LR" ? Position.Right : Position.Bottom,
        position: {
          x: position.x - NODE_WIDTH / 2,
          y: position.y - NODE_HEIGHT / 2,
        },
      };
    }),
    edges,
  };
}
