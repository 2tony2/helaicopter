export type AnalyticsReadBackend = "legacy" | "clickhouse";
export type ConversationSummaryReadBackend = "legacy" | "clickhouse";

export interface BackendFeatureFlags {
  useClickHouseAnalyticsReads: boolean;
  useClickHouseConversationSummaryReads: boolean;
  liveIngestionEnabled: boolean;
}

function readBooleanEnv(name: string): boolean {
  const value = process.env[name];
  if (!value) {
    return false;
  }

  return ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

const backendFeatureFlags: BackendFeatureFlags = {
  useClickHouseAnalyticsReads: readBooleanEnv(
    "HELAICOPTER_USE_CLICKHOUSE_ANALYTICS_READS"
  ),
  useClickHouseConversationSummaryReads: readBooleanEnv(
    "HELAICOPTER_USE_CLICKHOUSE_CONVERSATION_SUMMARIES"
  ),
  liveIngestionEnabled: readBooleanEnv("HELAICOPTER_ENABLE_LIVE_INGESTION"),
};

export function getBackendFeatureFlags(): BackendFeatureFlags {
  return backendFeatureFlags;
}

export function getAnalyticsReadBackend(): AnalyticsReadBackend {
  return backendFeatureFlags.useClickHouseAnalyticsReads
    ? "clickhouse"
    : "legacy";
}

export function getConversationSummaryReadBackend(): ConversationSummaryReadBackend {
  return backendFeatureFlags.useClickHouseConversationSummaryReads
    ? "clickhouse"
    : "legacy";
}
