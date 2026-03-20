import { z } from "zod";

import {
  isoDateString,
  nonEmptyTrimmedString,
  providerSchema,
} from "./shared.ts";

const trimmedString = z.string().trim();
const nullableTrimmedString = z.union([trimmedString, z.null()]);
const nullableFiniteNumber = z.union([z.number().finite(), z.null()]);

const evaluationScopeSchema = z.enum(["full", "failed_tool_calls", "guided_subset"]);
const evaluationStatusSchema = z.enum(["running", "completed", "failed"]);

const evaluationPromptSnakeSchema = z.object({
  prompt_id: nonEmptyTrimmedString,
  name: nonEmptyTrimmedString,
  description: nullableTrimmedString.optional(),
  prompt_text: nonEmptyTrimmedString,
  is_default: z.boolean(),
  created_at: isoDateString,
  updated_at: isoDateString,
});

const evaluationPromptCamelSchema = z.object({
  promptId: nonEmptyTrimmedString,
  name: nonEmptyTrimmedString,
  description: nullableTrimmedString.optional(),
  promptText: nonEmptyTrimmedString,
  isDefault: z.boolean(),
  createdAt: isoDateString,
  updatedAt: isoDateString,
});

export const evaluationPromptSchema = z.union([
  evaluationPromptSnakeSchema,
  evaluationPromptCamelSchema,
]);

export const evaluationPromptListSchema = z.array(evaluationPromptSchema);

const conversationEvaluationSnakeSchema = z.object({
  evaluation_id: nonEmptyTrimmedString,
  conversation_id: nonEmptyTrimmedString,
  prompt_id: z.union([nonEmptyTrimmedString, z.null()]),
  provider: providerSchema,
  model: nonEmptyTrimmedString,
  status: evaluationStatusSchema,
  scope: evaluationScopeSchema,
  selection_instruction: nullableTrimmedString,
  prompt_name: nonEmptyTrimmedString,
  prompt_text: nonEmptyTrimmedString,
  report_markdown: nullableTrimmedString,
  raw_output: nullableTrimmedString,
  error_message: nullableTrimmedString,
  command: nonEmptyTrimmedString,
  created_at: isoDateString,
  finished_at: z.union([isoDateString, z.null()]),
  duration_ms: nullableFiniteNumber,
});

const conversationEvaluationCamelSchema = z.object({
  evaluationId: nonEmptyTrimmedString,
  conversationId: nonEmptyTrimmedString,
  promptId: z.union([nonEmptyTrimmedString, z.null()]),
  provider: providerSchema,
  model: nonEmptyTrimmedString,
  status: evaluationStatusSchema,
  scope: evaluationScopeSchema,
  selectionInstruction: nullableTrimmedString,
  promptName: nonEmptyTrimmedString,
  promptText: nonEmptyTrimmedString,
  reportMarkdown: nullableTrimmedString,
  rawOutput: nullableTrimmedString,
  errorMessage: nullableTrimmedString,
  command: nonEmptyTrimmedString,
  createdAt: isoDateString,
  finishedAt: z.union([isoDateString, z.null()]),
  durationMs: nullableFiniteNumber,
});

export const conversationEvaluationSchema = z.union([
  conversationEvaluationSnakeSchema,
  conversationEvaluationCamelSchema,
]);

export const conversationEvaluationListSchema = z.array(conversationEvaluationSchema);

export const evaluationPromptWriteSchema = z.object({
  name: nonEmptyTrimmedString,
  description: z.union([trimmedString, z.null()]),
  promptText: nonEmptyTrimmedString,
});

export const conversationEvaluationCreateSchema = z.object({
  provider: providerSchema,
  model: nonEmptyTrimmedString,
  promptId: z.union([nonEmptyTrimmedString, z.null()]),
  promptName: nonEmptyTrimmedString,
  promptText: nonEmptyTrimmedString,
  scope: evaluationScopeSchema,
  selectionInstruction: z.union([trimmedString.min(1), z.null()]),
});

const promptSelectionSchema = z.union([
  z.literal("custom"),
  nonEmptyTrimmedString,
]);

const evaluationPromptWriteInputSchema = z.object({
  name: z.string(),
  description: z.string().nullable(),
  promptText: z.string(),
});

const conversationEvaluationCreateInputSchema = z
  .object({
    provider: providerSchema,
    model: nonEmptyTrimmedString,
    selectedPromptId: promptSelectionSchema,
    promptName: z.string(),
    promptText: z.string(),
    scope: evaluationScopeSchema,
    selectionInstruction: z.string(),
  })
  .superRefine((value, context) => {
    if (value.scope !== "guided_subset") {
      return;
    }

    if (!value.selectionInstruction.trim()) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "selectionInstruction is required for guided_subset scope.",
        path: ["selectionInstruction"],
      });
    }
  });

export function parseEvaluationPromptWriteInput(input: {
  name: string;
  description: string | null;
  promptText: string;
}) {
  const parsed = evaluationPromptWriteInputSchema.parse(input);

  return evaluationPromptWriteSchema.parse({
    name: parsed.name,
    description: parsed.description,
    promptText: parsed.promptText,
  });
}

export function parseConversationEvaluationCreateInput(input: {
  provider: z.input<typeof providerSchema>;
  model: string;
  selectedPromptId: string;
  promptName: string;
  promptText: string;
  scope: z.input<typeof evaluationScopeSchema>;
  selectionInstruction: string;
}) {
  const parsed = conversationEvaluationCreateInputSchema.parse(input);

  return conversationEvaluationCreateSchema.parse({
    provider: parsed.provider,
    model: parsed.model,
    promptId: parsed.selectedPromptId === "custom" ? null : parsed.selectedPromptId,
    promptName: parsed.promptName,
    promptText: parsed.promptText,
    scope: parsed.scope,
    selectionInstruction:
      parsed.scope === "guided_subset" ? parsed.selectionInstruction : null,
  });
}

export function formatEvaluationValidationError(
  error: unknown,
  fallback: string
): string {
  if (!(error instanceof z.ZodError)) {
    return error instanceof Error ? error.message : fallback;
  }

  const issue = error.issues[0];
  if (!issue) {
    return fallback;
  }

  const field = issue.path[0];
  if (typeof field === "string" && field.length > 0) {
    return `${field}: ${issue.message}`;
  }

  return issue.message || fallback;
}

export type EvaluationPromptPayload = z.infer<typeof evaluationPromptSchema>;
export type ConversationEvaluationPayload = z.infer<typeof conversationEvaluationSchema>;
