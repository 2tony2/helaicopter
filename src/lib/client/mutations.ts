import type {
  ConversationEvaluation,
  DatabaseStatus,
  EvaluationPrompt,
  SubscriptionSettings,
} from "@/lib/types";
import { databaseStatusSchema } from "./schemas/database.ts";
import {
  conversationEvaluationCreateSchema,
  conversationEvaluationSchema,
  evaluationPromptSchema,
  evaluationPromptWriteSchema,
} from "./schemas/evaluations.ts";
import {
  subscriptionSettingsSchema,
  subscriptionSettingsWriteSchema,
} from "./schemas/subscriptions.ts";
import * as endpoints from "./endpoints.ts";
import { del, patch, post } from "./fetcher.ts";
import {
  normalizeConversationEvaluation,
  normalizeDatabaseStatus,
  normalizeEvaluationPrompt,
  normalizeSubscriptionSettings,
} from "./normalize.ts";

type EvaluationPromptWriteInput = {
  name: string;
  description: string | null;
  promptText: string;
};

type DatabaseRefreshInput = {
  force: boolean;
  fullRebuild?: boolean;
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

type ConversationRequestOptions = {
  parentSessionId?: string;
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

function rejectInvalidInput(error: Error): Promise<never> {
  return Promise.reject(error);
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

  const parsedStatus = databaseStatusSchema.safeParse(payload);
  if (parsedStatus.success) {
    return normalizeDatabaseStatus(parsedStatus.data);
  }

  if (!response.ok) {
    throw new Error(readErrorMessage(payload) ?? `Request failed with status ${response.status}.`);
  }

  throw new Error("Database refresh returned an invalid response.");
}

export function createEvaluationPrompt(
  input: EvaluationPromptWriteInput
): Promise<EvaluationPrompt> {
  const parsedInput = evaluationPromptWriteSchema.safeParse(input);
  if (!parsedInput.success) {
    return rejectInvalidInput(parsedInput.error);
  }

  return post(
    endpoints.evaluationPrompts(),
    parsedInput.data,
    evaluationPromptSchema,
    normalizeEvaluationPrompt
  );
}

export function updateEvaluationPrompt(
  promptId: string,
  input: EvaluationPromptWriteInput
): Promise<EvaluationPrompt> {
  const parsedInput = evaluationPromptWriteSchema.safeParse(input);
  if (!parsedInput.success) {
    return rejectInvalidInput(parsedInput.error);
  }

  return patch(
    endpoints.evaluationPrompt(promptId),
    parsedInput.data,
    evaluationPromptSchema,
    normalizeEvaluationPrompt
  );
}

export function deleteEvaluationPrompt(promptId: string): Promise<unknown> {
  return del(endpoints.evaluationPrompt(promptId));
}

export function createConversationEvaluation(
  projectPath: string,
  sessionId: string,
  input: ConversationEvaluationCreateInput,
  opts?: ConversationRequestOptions
): Promise<ConversationEvaluation> {
  const parsedInput = conversationEvaluationCreateSchema.safeParse(input);
  if (!parsedInput.success) {
    return rejectInvalidInput(parsedInput.error);
  }

  return post(
    endpoints.conversationEvaluations(projectPath, sessionId, opts),
    parsedInput.data,
    conversationEvaluationSchema,
    normalizeConversationEvaluation
  );
}

export function saveSubscriptionSettings(
  input: SubscriptionSettings
): Promise<SubscriptionSettings> {
  const parsedInput = subscriptionSettingsWriteSchema.safeParse(input);
  if (!parsedInput.success) {
    return rejectInvalidInput(parsedInput.error);
  }

  return patch(
    endpoints.subscriptionSettings(),
    parsedInput.data,
    subscriptionSettingsSchema,
    normalizeSubscriptionSettings
  );
}
