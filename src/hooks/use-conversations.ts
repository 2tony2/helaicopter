"use client";

import useSWR from "swr";
import type {
  ConversationSummary,
  ProcessedConversation,
  ProjectInfo,
  AnalyticsData,
  ConversationEvaluation,
  ConversationDag,
  ConversationDagSummary,
  DatabaseStatus,
  EvaluationPrompt,
  OvernightOatsRunRecord,
  SubscriptionSettings,
} from "@/lib/types";
import * as endpoints from "@/lib/client/endpoints";
import { fetcher, requestJson } from "@/lib/client/fetcher";
import {
  normalizeAnalytics,
  normalizeConversationEvaluations,
  normalizeConversationDag,
  normalizeConversationDagSummaries,
  normalizeConversationDetail,
  normalizeConversations,
  normalizeDatabaseStatus,
  normalizeEvaluationPrompts,
  normalizeProjects,
  normalizeSubscriptionSettings,
  normalizeTasks,
} from "@/lib/client/normalize";

const swrOptions = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
};

const conversationSwrOptions = {
  ...swrOptions,
  refreshInterval: 3_000,
};

const analyticsSwrOptions = {
  ...swrOptions,
  refreshInterval: 15_000,
};

const projectsSwrOptions = {
  ...swrOptions,
  refreshInterval: 15_000,
};

export function useProjects() {
  return useSWR<ProjectInfo[]>(
    endpoints.projects(),
    (url: string) => requestJson(url, undefined, normalizeProjects),
    projectsSwrOptions
  );
}

export function useConversations(project?: string, days?: number) {
  return useSWR<ConversationSummary[]>(
    endpoints.conversations({ project, days }),
    (url: string) => requestJson(url, undefined, normalizeConversations),
    conversationSwrOptions
  );
}

export function useConversation(projectPath?: string, sessionId?: string) {
  const url =
    projectPath && sessionId
      ? endpoints.conversation(projectPath, sessionId)
      : null;
  return useSWR<ProcessedConversation>(
    url,
    (readUrl: string) => requestJson(readUrl, undefined, normalizeConversationDetail),
    conversationSwrOptions
  );
}

export function useConversationDag(projectPath?: string, sessionId?: string) {
  const url =
    projectPath && sessionId
      ? endpoints.conversationDag(projectPath, sessionId)
      : null;
  return useSWR<ConversationDag>(
    url,
    (readUrl: string) => requestJson(readUrl, undefined, normalizeConversationDag),
    conversationSwrOptions
  );
}

export function useConversationDagSummaries(
  project?: string,
  days?: number,
  provider?: string
) {
  return useSWR<ConversationDagSummary[]>(
    endpoints.conversationDags({ project, days, provider }),
    (url: string) => requestJson(url, undefined, normalizeConversationDagSummaries),
    conversationSwrOptions
  );
}

export function useOvernightOatsRuns() {
  return useSWR<OvernightOatsRunRecord[]>(
    endpoints.orchestrationOats(),
    fetcher,
    conversationSwrOptions
  );
}

export function useAnalytics(days?: number, provider?: string) {
  return useSWR<AnalyticsData>(
    endpoints.analytics({ days, provider }),
    (url: string) => requestJson(url, undefined, normalizeAnalytics),
    analyticsSwrOptions
  );
}

export function useTasks(sessionId?: string) {
  const url = sessionId ? endpoints.tasks(sessionId) : null;
  return useSWR<unknown[]>(
    url,
    (readUrl: string) => requestJson(readUrl, undefined, normalizeTasks),
    conversationSwrOptions
  );
}

export function useSubagentConversation(
  projectPath?: string,
  sessionId?: string,
  agentId?: string
) {
  const url =
    projectPath && sessionId && agentId
      ? endpoints.subagent(projectPath, sessionId, agentId)
      : null;
  return useSWR<ProcessedConversation>(
    url,
    (readUrl: string) => requestJson(readUrl, undefined, normalizeConversationDetail),
    conversationSwrOptions
  );
}

export function useDatabaseStatus() {
  return useSWR<DatabaseStatus>(
    endpoints.databaseStatus(),
    (url: string) => requestJson(url, undefined, normalizeDatabaseStatus),
    {
    ...swrOptions,
    refreshInterval: 300_000,
    }
  );
}

export function useEvaluationPrompts() {
  return useSWR<EvaluationPrompt[]>(
    endpoints.evaluationPrompts(),
    (url: string) => requestJson(url, undefined, normalizeEvaluationPrompts),
    swrOptions
  );
}

export function useConversationEvaluations(projectPath?: string, sessionId?: string) {
  const url =
    projectPath && sessionId
      ? endpoints.conversationEvaluations(projectPath, sessionId)
      : null;
  return useSWR<ConversationEvaluation[]>(
    url,
    (readUrl: string) => requestJson(readUrl, undefined, normalizeConversationEvaluations),
    {
    ...swrOptions,
    refreshInterval: (evaluations) =>
      evaluations?.some((evaluation) => evaluation.status === "running") ? 3_000 : 0,
    }
  );
}

export function useSubscriptionSettings() {
  return useSWR<SubscriptionSettings>(
    endpoints.subscriptionSettings(),
    (url: string) => requestJson(url, undefined, normalizeSubscriptionSettings),
    swrOptions
  );
}
