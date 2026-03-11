"use client";

import useSWR from "swr";
import type {
  ConversationSummary,
  ProcessedConversation,
  ProjectInfo,
  AnalyticsData,
} from "@/lib/types";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const swrOptions = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
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
  return useSWR<ConversationSummary[]>(url, fetcher, swrOptions);
}

export function useConversation(projectPath?: string, sessionId?: string) {
  const url =
    projectPath && sessionId
      ? `/api/conversations/${encodeURIComponent(projectPath)}/${sessionId}`
      : null;
  return useSWR<ProcessedConversation>(url, fetcher, swrOptions);
}

export function useAnalytics(days?: number, provider?: string) {
  const params = new URLSearchParams();
  if (days) params.set("days", String(days));
  if (provider && provider !== "all") params.set("provider", provider);
  const qs = params.toString();
  return useSWR<AnalyticsData>(`/api/analytics${qs ? `?${qs}` : ""}`, fetcher, swrOptions);
}

export function useTasks(sessionId?: string) {
  const url = sessionId ? `/api/tasks/${sessionId}` : null;
  return useSWR<unknown[]>(url, fetcher, swrOptions);
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
  return useSWR<ProcessedConversation>(url, fetcher, swrOptions);
}
