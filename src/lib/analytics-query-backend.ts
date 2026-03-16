import { getLegacyAnalytics } from "@/lib/claude-data";
import type { AnalyticsData } from "@/lib/types";

export interface AnalyticsQueryDebugInfo {
  requestedBackend: "legacy";
  resolvedBackend: "legacy";
  fallbackReason?: string;
  liveMergeApplied: boolean;
}

export interface AnalyticsQueryResult {
  analytics: AnalyticsData;
  debug: AnalyticsQueryDebugInfo;
}

export interface AnalyticsQueryBackend {
  name: "legacy";
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

export function getAnalyticsQueryBackend(): AnalyticsQueryBackend {
  return legacyAnalyticsQueryBackend;
}

export async function queryAnalytics(
  days?: number,
  provider?: string
): Promise<AnalyticsQueryResult> {
  return getAnalyticsQueryBackend().getAnalytics(days, provider);
}
