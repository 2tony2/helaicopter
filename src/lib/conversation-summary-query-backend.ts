import { getConversationSummaryReadBackend } from "@/lib/backend-flags";
import { listLegacyConversations } from "@/lib/claude-data";
import { queryClickHouseConversationSummaries } from "@/lib/clickhouse-conversation-summaries";
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
    async listConversations(projectFilter, days) {
      try {
        return await queryClickHouseConversationSummaries(projectFilter, days);
      } catch {
        return legacyConversationSummaryQueryBackend.listConversations(
          projectFilter,
          days
        );
      }
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
