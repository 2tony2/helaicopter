"use client";

import useSWR from "swr";
import type {
  ConversationSummary,
  ProcessedConversation,
  ProjectInfo,
  AnalyticsData,
  ConversationEvaluation,
  DatabaseStatus,
  EvaluationPrompt,
  SubscriptionSettings,
} from "@/lib/types";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const swrOptions = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
};

const liveSwrOptions = {
  ...swrOptions,
  refreshInterval: 30_000,
};

export function useProjects() {
  return useSWR<ProjectInfo[]>("/api/projects", fetcher, swrOptions);
}

export function useConversations(project?: string, days?: number) {
  const params = new URLSearchParams();
  if (project) params.set("project", project);
  if (days) params.set("days", String(days));
  const qs = params.toString();
  const url = `/api/conversations${qs ? `?${qs}` : ""}`;
  return useSWR<ConversationSummary[]>(url, fetcher, liveSwrOptions);
}

export function useConversation(projectPath?: string, sessionId?: string) {
  const url =
    projectPath && sessionId
      ? `/api/conversations/${encodeURIComponent(projectPath)}/${sessionId}`
      : null;
  return useSWR<ProcessedConversation>(url, fetcher, liveSwrOptions);
}

export function useAnalytics(days?: number, provider?: string) {
  const params = new URLSearchParams();
  if (days) params.set("days", String(days));
  if (provider && provider !== "all") params.set("provider", provider);
  const qs = params.toString();
  return useSWR<AnalyticsData>(`/api/analytics${qs ? `?${qs}` : ""}`, fetcher, liveSwrOptions);
}

export function useTasks(sessionId?: string) {
  const url = sessionId ? `/api/tasks/${sessionId}` : null;
  return useSWR<unknown[]>(url, fetcher, liveSwrOptions);
}

export function useSubagentConversation(
  projectPath?: string,
  sessionId?: string,
  agentId?: string
) {
  const url =
    projectPath && sessionId && agentId
      ? `/api/subagents/${encodeURIComponent(projectPath)}/${sessionId}/${agentId}`
      : null;
  return useSWR<ProcessedConversation>(url, fetcher, liveSwrOptions);
}

export function useDatabaseStatus() {
  return useSWR<DatabaseStatus>("/api/databases/status", fetcher, {
    ...swrOptions,
    refreshInterval: 300_000,
  });
}

export function useEvaluationPrompts() {
  return useSWR<EvaluationPrompt[]>("/api/evaluation-prompts", fetcher, swrOptions);
}

export function useConversationEvaluations(projectPath?: string, sessionId?: string) {
  const url =
    projectPath && sessionId
      ? `/api/conversations/${encodeURIComponent(projectPath)}/${sessionId}/evaluations`
      : null;
  return useSWR<ConversationEvaluation[]>(url, fetcher, {
    ...swrOptions,
    refreshInterval: (evaluations) =>
      evaluations?.some((evaluation) => evaluation.status === "running") ? 3_000 : 0,
  });
}

export function useSubscriptionSettings() {
  return useSWR<SubscriptionSettings>("/api/subscription-settings", fetcher, swrOptions);
}
