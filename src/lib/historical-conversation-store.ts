import {
  getHistoricalConversation as getSqliteHistoricalConversation,
  getHistoricalTasksForSession as getSqliteHistoricalTasksForSession,
  hasHistoricalConversation as hasSqliteHistoricalConversation,
  listHistoricalConversationSummaries as listSqliteHistoricalConversationSummaries,
} from "@/lib/conversation-db";
import type { ConversationSummary, ProcessedConversation } from "@/lib/types";

export interface HistoricalConversationStore {
  listConversationSummaries(
    projectFilter?: string,
    days?: number
  ): ConversationSummary[];
  getConversation(
    projectPath: string,
    sessionId: string
  ): ProcessedConversation | null;
  getTasksForSession(sessionId: string): unknown[] | null;
  hasConversation(projectPath: string, sessionId: string): boolean;
}

const sqliteHistoricalConversationStore: HistoricalConversationStore = {
  listConversationSummaries(projectFilter, days) {
    return listSqliteHistoricalConversationSummaries(projectFilter, days);
  },
  getConversation(projectPath, sessionId) {
    return getSqliteHistoricalConversation(projectPath, sessionId);
  },
  getTasksForSession(sessionId) {
    return getSqliteHistoricalTasksForSession(sessionId);
  },
  hasConversation(projectPath, sessionId) {
    return hasSqliteHistoricalConversation(projectPath, sessionId);
  },
};

export function getHistoricalConversationStore(): HistoricalConversationStore {
  return sqliteHistoricalConversationStore;
}
