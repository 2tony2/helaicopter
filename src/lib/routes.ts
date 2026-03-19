export const conversationDetailTabs = [
  "messages",
  "plans",
  "evaluations",
  "failed",
  "context",
  "dag",
  "subagents",
  "tasks",
  "raw",
] as const;

export type ConversationDetailTab = (typeof conversationDetailTabs)[number];

export const orchestrationTabs = [
  "conversation-dags",
  "prefect",
  "prefect-ui",
] as const;

export type OrchestrationTab = (typeof orchestrationTabs)[number];

export const PREFECT_UI_URL = "http://127.0.0.1:4200";

export function resolveConversationDetailTab(value?: string): ConversationDetailTab {
  return (conversationDetailTabs as readonly string[]).includes(value ?? "")
    ? (value as ConversationDetailTab)
    : "messages";
}

export function resolveOrchestrationInitialTab(value?: string): OrchestrationTab {
  return (orchestrationTabs as readonly string[]).includes(value ?? "")
    ? (value as OrchestrationTab)
    : "prefect";
}

export function normalizePrefectUiPath(value?: string): string | undefined {
  if (!value) {
    return undefined;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

export function buildPrefectUiUrl(prefectPath?: string): string {
  const normalizedPath = normalizePrefectUiPath(prefectPath);
  return normalizedPath ? `${PREFECT_UI_URL}${normalizedPath}` : PREFECT_UI_URL;
}

export function getConversationRouteState(
  searchParams: URLSearchParams,
  initial?: {
    tab?: string;
    plan?: string;
    subagent?: string;
  }
): {
  tab: ConversationDetailTab;
  plan?: string;
  subagent?: string;
} {
  const plan = searchParams.get("plan") ?? initial?.plan;
  const subagent = searchParams.get("subagent") ?? initial?.subagent;

  return {
    tab: resolveConversationDetailTab(searchParams.get("tab") ?? initial?.tab),
    plan: plan ?? undefined,
    subagent: subagent ?? undefined,
  };
}

export function buildConversationRoute(
  projectPath: string,
  sessionId: string,
  opts?: {
    tab?: ConversationDetailTab;
    plan?: string;
    subagent?: string;
  }
): string {
  const params = new URLSearchParams();
  if (opts?.tab && opts.tab !== "messages") {
    params.set("tab", opts.tab);
  }
  if (opts?.plan) {
    params.set("plan", opts.plan);
  }
  if (opts?.subagent) {
    params.set("subagent", opts.subagent);
  }
  const query = params.toString();
  const path = `/conversations/${encodeURIComponent(projectPath)}/${sessionId}`;
  return query ? `${path}?${query}` : path;
}

export function buildConversationSubagentRoute(
  projectPath: string,
  sessionId: string,
  agentId: string,
): string {
  return `/conversations/${encodeURIComponent(projectPath)}/${sessionId}/subagents/${agentId}`;
}

export function buildOrchestrationRoute(opts?: {
  tab?: OrchestrationTab;
  flowRunId?: string;
  prefectPath?: string;
}): string {
  const params = new URLSearchParams();
  if (opts?.tab && opts.tab !== "prefect") {
    params.set("tab", opts.tab);
  }
  if (opts?.flowRunId) {
    params.set("flowRunId", opts.flowRunId);
  }
  const normalizedPrefectPath = normalizePrefectUiPath(opts?.prefectPath);
  if (normalizedPrefectPath) {
    params.set("prefectPath", normalizedPrefectPath);
  }
  const query = params.toString();
  return query ? `/orchestration?${query}` : "/orchestration";
}

export function getOrchestrationRouteState(
  searchParams: URLSearchParams,
  initial?: {
    tab?: string;
    flowRunId?: string;
    prefectPath?: string;
  }
): {
  tab: OrchestrationTab;
  flowRunId?: string;
  prefectPath?: string;
} {
  const prefectPath = normalizePrefectUiPath(
    searchParams.get("prefectPath") ?? initial?.prefectPath
  );
  const flowRunId = searchParams.get("flowRunId") ?? initial?.flowRunId;

  return {
    tab: resolveOrchestrationInitialTab(searchParams.get("tab") ?? initial?.tab),
    flowRunId: flowRunId ?? undefined,
    prefectPath,
  };
}
