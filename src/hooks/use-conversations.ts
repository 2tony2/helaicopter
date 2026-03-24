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
  ConversationRouteResolution,
  DatabaseStatus,
  EvaluationPrompt,
  OvernightOatsRunRecord,
  SubscriptionSettings,
} from "@/lib/types";
import * as endpoints from "@/lib/client/endpoints";
import { requestJson } from "@/lib/client/fetcher";
import {
  normalizeAnalytics,
  normalizeConversationEvaluations,
  normalizeConversationDag,
  normalizeConversationDagSummaries,
  normalizeConversationDetail,
  normalizeConversationRouteResolution,
  normalizeConversations,
  normalizeDatabaseStatus,
  normalizeEvaluationPrompts,
  normalizeOvernightOatsRuns,
  normalizeProjects,
  normalizeSubscriptionSettings,
  normalizeTasks,
} from "@/lib/client/normalize";
import { databaseStatusSchema } from "@/lib/client/schemas/database";
import { conversationSummaryListSchema } from "@/lib/client/schemas/conversations";
import {
  conversationEvaluationListSchema,
  evaluationPromptListSchema,
} from "@/lib/client/schemas/evaluations";
import { subscriptionSettingsSchema } from "@/lib/client/schemas/subscriptions";

const swrOptions = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
};

const liveConversationSwrOptions = {
  ...swrOptions,
  // Detail polling remains at 5s; backend discovery caching keeps OpenClaw refreshes bounded.
  refreshInterval: 5_000,
};

const analyticsSwrOptions = {
  ...swrOptions,
  refreshInterval: 15_000,
};

const projectsSwrOptions = liveConversationSwrOptions;

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
    (url: string) =>
      requestJson(url, undefined, conversationSummaryListSchema, normalizeConversations),
    liveConversationSwrOptions
  );
}

export function useConversation(
  projectPath?: string,
  sessionId?: string,
  parentSessionId?: string
) {
  const url =
    projectPath && sessionId
      ? endpoints.conversation(projectPath, sessionId, { parentSessionId })
      : null;
  return useSWR<ProcessedConversation>(
    url,
    (readUrl: string) => requestJson(readUrl, undefined, normalizeConversationDetail),
    liveConversationSwrOptions
  );
}

export function useConversationRouteResolution(conversationRef?: string) {
  const url = conversationRef ? endpoints.conversationByRef(conversationRef) : null;
  return useSWR<ConversationRouteResolution>(
    url,
    (readUrl: string) => requestJson(readUrl, undefined, normalizeConversationRouteResolution),
    swrOptions
  );
}

export function useConversationDag(
  projectPath?: string,
  sessionId?: string,
  parentSessionId?: string
) {
  const url =
    projectPath && sessionId
      ? endpoints.conversationDag(projectPath, sessionId, { parentSessionId })
      : null;
  return useSWR<ConversationDag>(
    url,
    (readUrl: string) => requestJson(readUrl, undefined, normalizeConversationDag),
    swrOptions
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
    liveConversationSwrOptions
  );
}

export function useOvernightOatsRuns() {
  return useSWR<OvernightOatsRunRecord[]>(
    endpoints.orchestrationOats(),
    (url: string) => requestJson(url, undefined, normalizeOvernightOatsRuns),
    liveConversationSwrOptions
  );
}

export function useAnalytics(days?: number, provider?: string) {
  return useSWR<AnalyticsData>(
    endpoints.analytics({ days, provider }),
    (url: string) => requestJson(url, undefined, normalizeAnalytics),
    analyticsSwrOptions
  );
}

export function useTasks(sessionId?: string, parentSessionId?: string) {
  const url = sessionId ? endpoints.tasks(sessionId, { parentSessionId }) : null;
  return useSWR<unknown[]>(
    url,
    (readUrl: string) => requestJson(readUrl, undefined, normalizeTasks),
    liveConversationSwrOptions
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
    liveConversationSwrOptions
  );
}

export function useDatabaseStatus() {
  return useSWR<DatabaseStatus>(
    endpoints.databaseStatus(),
    (url: string) =>
      requestJson(url, undefined, databaseStatusSchema, normalizeDatabaseStatus),
    {
      ...swrOptions,
      refreshInterval: 30_000,
    }
  );
}

export function useEvaluationPrompts() {
  return useSWR<EvaluationPrompt[]>(
    endpoints.evaluationPrompts(),
    (url: string) =>
      requestJson(url, undefined, evaluationPromptListSchema, normalizeEvaluationPrompts),
    swrOptions
  );
}

export function useConversationEvaluations(
  projectPath?: string,
  sessionId?: string,
  parentSessionId?: string
) {
  const url =
    projectPath && sessionId
      ? endpoints.conversationEvaluations(projectPath, sessionId, { parentSessionId })
      : null;
  return useSWR<ConversationEvaluation[]>(
    url,
    (readUrl: string) =>
      requestJson(
        readUrl,
        undefined,
        conversationEvaluationListSchema,
        normalizeConversationEvaluations
      ),
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
    (url: string) =>
      requestJson(url, undefined, subscriptionSettingsSchema, normalizeSubscriptionSettings),
    swrOptions
  );
}
