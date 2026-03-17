import {
  getConversation,
  getSubagentConversation,
  listLegacyConversations,
} from "./claude-data";
import type {
  ConversationDag,
  ConversationDagEdge,
  ConversationDagNode,
  ConversationDagStats,
  ConversationDagSummary,
  ProcessedConversation,
  SubagentInfo,
  SupportedProvider,
} from "./types";

function totalConversationTokens(conversation: ProcessedConversation): number {
  return (
    (conversation.totalUsage.input_tokens || 0) +
    (conversation.totalUsage.output_tokens || 0) +
    (conversation.totalUsage.cache_creation_input_tokens || 0) +
    (conversation.totalUsage.cache_read_input_tokens || 0)
  );
}

function summarizeConversationLabel(
  conversation: ProcessedConversation | null,
  fallback: string
): string {
  if (!conversation) {
    return fallback;
  }

  for (const message of conversation.messages) {
    for (const block of message.blocks) {
      if (block.type === "text" && block.text.trim()) {
        return block.text.trim().replace(/\s+/g, " ").slice(0, 120);
      }
    }
  }

  return fallback;
}

function buildConversationPath(projectPath: string, sessionId: string): string {
  return `/conversations/${encodeURIComponent(projectPath)}/${sessionId}`;
}

function toNode(
  projectPath: string,
  sessionId: string,
  depth: number,
  parentSessionId: string | undefined,
  conversation: ProcessedConversation | null,
  subagent: SubagentInfo | undefined,
  isRoot: boolean
): ConversationDagNode {
  const fallbackLabel =
    subagent?.nickname ||
    subagent?.description ||
    `${isRoot ? "Conversation" : "Sub-agent"} ${sessionId.slice(0, 8)}`;

  return {
    id: sessionId,
    sessionId,
    parentSessionId,
    projectPath,
    label: summarizeConversationLabel(conversation, fallbackLabel),
    description: subagent?.description,
    nickname: subagent?.nickname,
    subagentType: subagent?.subagentType,
    threadType: isRoot ? "main" : "subagent",
    hasTranscript: Boolean(conversation),
    model: conversation?.model,
    messageCount: conversation?.messages.length ?? 0,
    totalTokens: conversation ? totalConversationTokens(conversation) : 0,
    timestamp: conversation?.lastUpdatedAt ?? 0,
    depth,
    path: buildConversationPath(projectPath, sessionId),
    isRoot,
  };
}

function computeStats(
  rootSessionId: string,
  nodes: ConversationDagNode[],
  edges: ConversationDagEdge[]
): ConversationDagStats {
  const breadthMap = new Map<number, number>();
  const outDegree = new Map<string, number>();

  for (const node of nodes) {
    breadthMap.set(node.depth, (breadthMap.get(node.depth) || 0) + 1);
    outDegree.set(node.id, 0);
  }

  for (const edge of edges) {
    outDegree.set(edge.source, (outDegree.get(edge.source) || 0) + 1);
  }

  const maxBreadth = Math.max(0, ...breadthMap.values());
  const maxDepth = Math.max(0, ...nodes.map((node) => node.depth));
  const leafCount = nodes.filter((node) => (outDegree.get(node.id) || 0) === 0).length;
  const rootSubagentCount = outDegree.get(rootSessionId) || 0;

  return {
    totalNodes: nodes.length,
    totalEdges: edges.length,
    totalSubagentNodes: nodes.filter((node) => !node.isRoot).length,
    maxDepth,
    maxBreadth,
    leafCount,
    rootSubagentCount,
    totalMessages: nodes.reduce((sum, node) => sum + node.messageCount, 0),
    totalTokens: nodes.reduce((sum, node) => sum + node.totalTokens, 0),
  };
}

export async function buildConversationDag(
  projectPath: string,
  rootSessionId: string
): Promise<ConversationDag | null> {
  const nodes = new Map<string, ConversationDagNode>();
  const edges = new Map<string, ConversationDagEdge>();
  const expanded = new Set<string>();
  const activePath = new Set<string>();

  async function visitThread(
    sessionId: string,
    depth: number,
    parentSessionId?: string,
    subagent?: SubagentInfo
  ): Promise<void> {
    if (parentSessionId) {
      const edgeId = `${parentSessionId}->${sessionId}`;
      edges.set(edgeId, {
        id: edgeId,
        source: parentSessionId,
        target: sessionId,
      });
    }

    const existingNode = nodes.get(sessionId);
    if (existingNode && existingNode.depth <= depth && expanded.has(sessionId)) {
      return;
    }

    const shouldLoadConversation = subagent?.hasFile !== false || !subagent;
    const conversation = shouldLoadConversation
      ? parentSessionId
        ? await getSubagentConversation(projectPath, parentSessionId, sessionId)
        : await getConversation(projectPath, sessionId)
      : null;
    const nextNode = toNode(
      projectPath,
      sessionId,
      existingNode ? Math.min(existingNode.depth, depth) : depth,
      parentSessionId,
      conversation,
      subagent,
      !parentSessionId
    );
    nodes.set(sessionId, existingNode ? { ...existingNode, ...nextNode } : nextNode);

    if (!conversation || expanded.has(sessionId) || activePath.has(sessionId)) {
      return;
    }

    activePath.add(sessionId);
    expanded.add(sessionId);

    for (const child of conversation.subagents) {
      if (child.agentId === sessionId) {
        continue;
      }
      await visitThread(child.agentId, nextNode.depth + 1, sessionId, child);
    }

    activePath.delete(sessionId);
  }

  await visitThread(rootSessionId, 0);

  const rootNode = nodes.get(rootSessionId);
  if (!rootNode) {
    return null;
  }

  const orderedNodes = Array.from(nodes.values()).sort((a, b) => {
    if (a.depth !== b.depth) {
      return a.depth - b.depth;
    }
    return (a.timestamp || 0) - (b.timestamp || 0) || a.id.localeCompare(b.id);
  });
  const orderedEdges = Array.from(edges.values()).sort((a, b) =>
    a.id.localeCompare(b.id)
  );

  return {
    projectPath,
    rootSessionId,
    nodes: orderedNodes,
    edges: orderedEdges,
    stats: computeStats(rootSessionId, orderedNodes, orderedEdges),
  };
}

export async function listConversationDagSummaries(
  projectFilter?: string,
  days?: number,
  provider?: SupportedProvider
): Promise<ConversationDagSummary[]> {
  const conversations = await listLegacyConversations(projectFilter, days);
  const mainsWithSubagents = conversations.filter((conversation) => {
    if (conversation.threadType !== "main" || conversation.subagentCount === 0) {
      return false;
    }
    if (provider === "codex") {
      return conversation.projectPath.startsWith("codex:");
    }
    if (provider === "claude") {
      return !conversation.projectPath.startsWith("codex:");
    }
    return true;
  });

  const summaries = await Promise.all(
    mainsWithSubagents.map(async (conversation) => {
      const dag = await buildConversationDag(
        conversation.projectPath,
        conversation.sessionId
      );
      if (!dag) {
        return null;
      }
      return {
        ...conversation,
        dag: dag.stats,
      } satisfies ConversationDagSummary;
    })
  );

  return summaries
    .filter((summary): summary is ConversationDagSummary => summary !== null)
    .sort((a, b) => b.lastUpdatedAt - a.lastUpdatedAt);
}
