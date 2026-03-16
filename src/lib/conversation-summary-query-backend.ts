import { listLegacyConversations } from "@/lib/claude-data";
import type { ConversationSummary } from "@/lib/types";

export interface ConversationSummaryQueryBackend {
  name: "legacy";
  listConversations(
    projectFilter?: string,
    days?: number
  ): Promise<ConversationSummary[]>;
}

const legacyConversationSummaryQueryBackend: ConversationSummaryQueryBackend = {
  name: "legacy",
  listConversations(projectFilter, days) {
    return listLegacyConversations(projectFilter, days);
  },
};

export function getConversationSummaryQueryBackend(): ConversationSummaryQueryBackend {
  return legacyConversationSummaryQueryBackend;
}

export async function queryConversationSummaries(
  projectFilter?: string,
  days?: number
): Promise<ConversationSummary[]> {
  return getConversationSummaryQueryBackend().listConversations(
    projectFilter,
    days
  );
}
