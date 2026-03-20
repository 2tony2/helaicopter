import {
  conversationDetailTabs,
  orchestrationTabs,
  parsePrefectPath,
  resolveConversationDetailTab,
  resolveOrchestrationInitialTab,
  type ConversationDetailTab,
  type OrchestrationTab,
} from "./client/schemas/runtime.ts";

export {
  conversationDetailTabs,
  orchestrationTabs,
  resolveConversationDetailTab,
  resolveOrchestrationInitialTab,
};
export type { ConversationDetailTab, OrchestrationTab };

export const PREFECT_UI_URL = "http://127.0.0.1:4200";

export function normalizePrefectUiPath(value?: string): string | undefined {
  return parsePrefectPath(value);
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
    message?: string;
  }
): {
  tab: ConversationDetailTab;
  plan?: string;
  subagent?: string;
  message?: string;
} {
  const plan = searchParams.get("plan") ?? initial?.plan;
  const subagent = searchParams.get("subagent") ?? initial?.subagent;
  const message = searchParams.get("message") ?? initial?.message;

  return {
    tab: resolveConversationDetailTab(searchParams.get("tab") ?? initial?.tab),
    plan: plan ?? undefined,
    subagent: subagent ?? undefined,
    message: message ?? undefined,
  };
}

export function buildConversationRoute(
  projectPath: string,
  sessionId: string,
  opts?: {
    tab?: ConversationDetailTab;
    plan?: string;
    subagent?: string;
    message?: string;
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
  if (opts?.message) {
    params.set("message", opts.message);
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
  if (opts?.tab && opts.tab !== "orchestration") {
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
  const prefectPath = searchParams.has("prefectPath")
    ? normalizePrefectUiPath(searchParams.get("prefectPath") ?? undefined)
    : normalizePrefectUiPath(initial?.prefectPath);
  const flowRunId = searchParams.get("flowRunId") ?? initial?.flowRunId;

  return {
    tab: resolveOrchestrationInitialTab(searchParams.get("tab") ?? initial?.tab),
    flowRunId: flowRunId ?? undefined,
    prefectPath,
  };
}
