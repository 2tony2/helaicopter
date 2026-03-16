import { getAnalyticsReadBackend } from "@/lib/backend-flags";
import { getLegacyAnalytics } from "@/lib/claude-data";
import { queryClickHouseAnalyticsWithLiveFallback } from "@/lib/clickhouse-analytics";
import type { AnalyticsData } from "@/lib/types";
import { getBackendFeatureFlags } from "@/lib/backend-flags";

export interface AnalyticsQueryDebugInfo {
  requestedBackend: "legacy" | "clickhouse";
  resolvedBackend: "legacy" | "clickhouse";
  fallbackReason?: string;
  liveMergeApplied: boolean;
}

export interface AnalyticsQueryResult {
  analytics: AnalyticsData;
  debug: AnalyticsQueryDebugInfo;
}

export interface AnalyticsQueryBackend {
  name: "legacy" | "clickhouse";
  getAnalytics(days?: number, provider?: string): Promise<AnalyticsQueryResult>;
}

const legacyAnalyticsQueryBackend: AnalyticsQueryBackend = {
  name: "legacy",
  async getAnalytics(days, provider) {
    return {
      analytics: await getLegacyAnalytics(days, provider),
      debug: {
        requestedBackend: "legacy",
        resolvedBackend: "legacy",
        liveMergeApplied: false,
      },
    };
  },
};

const clickHouseAnalyticsQueryBackend: AnalyticsQueryBackend = {
  name: "clickhouse",
  async getAnalytics(days, provider) {
    try {
      const analytics = await queryClickHouseAnalyticsWithLiveFallback(days, provider, {
        liveIngestionEnabled: getBackendFeatureFlags().liveIngestionEnabled,
      });
      return {
        analytics: analytics.analytics,
        debug: {
          requestedBackend: "clickhouse",
          resolvedBackend: "clickhouse",
          liveMergeApplied: !getBackendFeatureFlags().liveIngestionEnabled,
        },
      };
    } catch (error) {
      const fallback = await legacyAnalyticsQueryBackend.getAnalytics(days, provider);
      return {
        analytics: fallback.analytics,
        debug: {
          requestedBackend: "clickhouse",
          resolvedBackend: "legacy",
          fallbackReason:
            error instanceof Error ? error.message : "ClickHouse analytics query failed",
          liveMergeApplied: false,
        },
      };
    }
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
): Promise<AnalyticsQueryResult> {
  return getAnalyticsQueryBackend().getAnalytics(days, provider);
}
