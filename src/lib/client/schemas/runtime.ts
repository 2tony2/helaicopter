import { z } from "zod";

const trimmedString = z.string().trim();
const absoluteUrlSchema = trimmedString.url("Expected an absolute URL.");
const schemePrefixPattern = /^[a-zA-Z][a-zA-Z\d+.-]*:/;

function stripTrailingSlashes(value: string) {
  return value.replace(/\/+$/, "");
}

function ensureLeadingSlash(value: string) {
  return value.startsWith("/") ? value : `/${value}`;
}

export const conversationDetailTabs = [
  "messages",
  "plans",
  "evaluations",
  "failed",
  "context",
  "dag",
  "subagents",
  "tasks",
  "openclaw",
  "raw",
] as const;

export type ConversationDetailTab = (typeof conversationDetailTabs)[number];

export const orchestrationTabs = [
  "conversation-dags",
  "orchestration",
  "prefect-ui",
] as const;

export type OrchestrationTab = (typeof orchestrationTabs)[number];

export const apiBaseUrlSchema = z.union([
  z.undefined().transform(() => ""),
  z.null().transform(() => ""),
  trimmedString.length(0).transform(() => ""),
  absoluteUrlSchema.transform(stripTrailingSlashes),
]);

export const prefectPathSchema = z.union([
  z.undefined().transform(() => undefined),
  z.null().transform(() => undefined),
  trimmedString.length(0).transform(() => undefined),
  trimmedString
    .refine(
      (value) => !value.startsWith("//") && !schemePrefixPattern.test(value),
      "Expected a relative Prefect UI path."
    )
    .transform(ensureLeadingSlash),
]);

export const conversationDetailTabSchema = z.enum(conversationDetailTabs);
export const orchestrationTabSchema = z.enum(orchestrationTabs);

export function parseApiBaseUrl(value?: string | null): string {
  const pre = typeof value === "string" ? stripTrailingSlashes(value.trim()) : value;
  const result = apiBaseUrlSchema.safeParse(pre);
  return result.success ? result.data : "";
}

export function parsePrefectPath(value?: string | null): string | undefined {
  const result = prefectPathSchema.safeParse(value);
  return result.success ? result.data : undefined;
}

export function resolveConversationDetailTab(value?: string): ConversationDetailTab {
  const result = conversationDetailTabSchema.safeParse(value);
  return result.success ? result.data : "messages";
}

export function resolveOrchestrationInitialTab(value?: string): OrchestrationTab {
  const result = orchestrationTabSchema.safeParse(value);
  return result.success ? result.data : "orchestration";
}
