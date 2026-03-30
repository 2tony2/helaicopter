import type { FrontendProvider } from "./types";

type ConversationSummaryTotals = {
  provider?: FrontendProvider;
  projectPath: string;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheCreationTokens: number;
  totalCacheReadTokens: number;
};

export function inferConversationProvider(projectPath: string): FrontendProvider {
  if (projectPath.startsWith("codex:")) return "codex";
  if (projectPath.startsWith("openclaw:")) return "openclaw";
  return "claude";
}

export function totalTokensForConversationSummary(
  conversation: ConversationSummaryTotals
): number {
  const provider =
    conversation.provider ?? inferConversationProvider(conversation.projectPath);
  if (provider === "codex") {
    return conversation.totalInputTokens + conversation.totalOutputTokens;
  }
  return (
    conversation.totalInputTokens +
    conversation.totalOutputTokens +
    conversation.totalCacheCreationTokens +
    conversation.totalCacheReadTokens
  );
}
