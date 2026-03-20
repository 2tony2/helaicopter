import type {
  ConversationEvaluation,
  DatabaseStatus,
  EvaluationPrompt,
  OvernightOatsRunRecord,
  SubscriptionSettings,
} from "@/lib/types";
import * as endpoints from "./endpoints";
import { del, patch, post } from "./fetcher";
import {
  normalizeConversationEvaluations,
  normalizeDatabaseStatus,
  normalizeEvaluationPrompts,
  normalizeOvernightOatsRun,
  normalizeSubscriptionSettings,
} from "./normalize";

type EvaluationPromptWriteInput = {
  name: string;
  description: string | null;
  promptText: string;
};

type DatabaseRefreshInput = {
  force: boolean;
  trigger: string;
  staleAfterSeconds?: number;
};

type ConversationEvaluationCreateInput = {
  provider: ConversationEvaluation["provider"];
  model: string;
  promptId: string | null;
  promptName: string;
  promptText: string;
  scope: ConversationEvaluation["scope"];
  selectionInstruction: string | null;
};

function readErrorMessage(payload: unknown): string | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }

  const body = payload as Record<string, unknown>;

  if (typeof body.error === "string" && body.error.trim()) {
    return body.error;
  }

  if (typeof body.detail === "string" && body.detail.trim()) {
    return body.detail;
  }

  return null;
}

export async function refreshDatabase(input: DatabaseRefreshInput): Promise<DatabaseStatus> {
  const response = await fetch(endpoints.databaseRefresh(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });
  const payload = await response.json().catch(() => null);

  if (payload && typeof payload === "object" && "status" in payload) {
    return normalizeDatabaseStatus(payload);
  }

  if (!response.ok) {
    throw new Error(readErrorMessage(payload) ?? `Request failed with status ${response.status}.`);
  }

  throw new Error("Database refresh returned an invalid response.");
}

export function createEvaluationPrompt(
  input: EvaluationPromptWriteInput
): Promise<EvaluationPrompt> {
  return post(endpoints.evaluationPrompts(), input, (value) =>
    normalizeEvaluationPrompts([value])[0]
  );
}

export function updateEvaluationPrompt(
  promptId: string,
  input: EvaluationPromptWriteInput
): Promise<EvaluationPrompt> {
  return patch(endpoints.evaluationPrompt(promptId), input, (value) =>
    normalizeEvaluationPrompts([value])[0]
  );
}

export function deleteEvaluationPrompt(promptId: string): Promise<unknown> {
  return del(endpoints.evaluationPrompt(promptId));
}

export function createConversationEvaluation(
  projectPath: string,
  sessionId: string,
  input: ConversationEvaluationCreateInput
): Promise<ConversationEvaluation> {
  return post(endpoints.conversationEvaluations(projectPath, sessionId), input, (value) =>
    normalizeConversationEvaluations([value])[0]
  );
}

export function saveSubscriptionSettings(
  input: SubscriptionSettings
): Promise<SubscriptionSettings> {
  return patch(endpoints.subscriptionSettings(), input, normalizeSubscriptionSettings);
}

export function refreshOvernightOatsRun(runId: string): Promise<OvernightOatsRunRecord> {
  return post(endpoints.orchestrationOatsRefresh(runId), undefined, normalizeOvernightOatsRun);
}

export function resumeOvernightOatsRun(runId: string): Promise<OvernightOatsRunRecord> {
  return post(endpoints.orchestrationOatsResume(runId), undefined, normalizeOvernightOatsRun);
}
