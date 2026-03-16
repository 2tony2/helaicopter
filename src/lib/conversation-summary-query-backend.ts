import { getConversationSummaryReadBackend } from "@/lib/backend-flags";
import { listLegacyConversations } from "@/lib/claude-data";
import type { ConversationSummary } from "@/lib/types";

export interface ConversationSummaryQueryBackend {
  name: "legacy" | "clickhouse";
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

const clickHouseConversationSummaryQueryBackend: ConversationSummaryQueryBackend =
  {
    name: "clickhouse",
    listConversations(projectFilter, days) {
      // Ticket 07 replaces this fallback with ClickHouse latest-state reads.
      return legacyConversationSummaryQueryBackend.listConversations(
        projectFilter,
        days
      );
    },
  };

export function getConversationSummaryQueryBackend(): ConversationSummaryQueryBackend {
  return getConversationSummaryReadBackend() === "clickhouse"
    ? clickHouseConversationSummaryQueryBackend
    : legacyConversationSummaryQueryBackend;
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
