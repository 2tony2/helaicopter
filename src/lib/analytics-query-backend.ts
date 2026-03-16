import { getAnalyticsReadBackend } from "@/lib/backend-flags";
import { getLegacyAnalytics } from "@/lib/claude-data";
import type { AnalyticsData } from "@/lib/types";

export interface AnalyticsQueryBackend {
  name: "legacy" | "clickhouse";
  getAnalytics(days?: number, provider?: string): Promise<AnalyticsData>;
}

const legacyAnalyticsQueryBackend: AnalyticsQueryBackend = {
  name: "legacy",
  getAnalytics(days, provider) {
    return getLegacyAnalytics(days, provider);
  },
};

const clickHouseAnalyticsQueryBackend: AnalyticsQueryBackend = {
  name: "clickhouse",
  getAnalytics(days, provider) {
    // Ticket 04 replaces this fallback with real ClickHouse queries.
    return legacyAnalyticsQueryBackend.getAnalytics(days, provider);
  },
};

export function getAnalyticsQueryBackend(): AnalyticsQueryBackend {
  return getAnalyticsReadBackend() === "clickhouse"
    ? clickHouseAnalyticsQueryBackend
    : legacyAnalyticsQueryBackend;
}

export async function queryAnalytics(
  days?: number,
  provider?: string
): Promise<AnalyticsData> {
  return getAnalyticsQueryBackend().getAnalytics(days, provider);
}
