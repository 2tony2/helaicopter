import { NextResponse } from "next/server";
import { getLegacyAnalytics } from "@/lib/claude-data";
import { queryAnalytics } from "@/lib/analytics-query-backend";
import type { AnalyticsData } from "@/lib/types";

const NUMERIC_COMPARISON_FIELDS = [
  "totalConversations",
  "totalInputTokens",
  "totalOutputTokens",
  "totalCacheCreationTokens",
  "totalCacheReadTokens",
  "totalReasoningTokens",
  "totalToolCalls",
  "totalFailedToolCalls",
  "estimatedCost",
] as const;

function readBooleanParam(value: string | null): boolean {
  if (!value) {
    return false;
  }

  return ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

function buildComparisonSummary(current: AnalyticsData, legacy: AnalyticsData) {
  const fields = Object.fromEntries(
    NUMERIC_COMPARISON_FIELDS.map((field) => {
      const currentValue = current[field];
      const legacyValue = legacy[field];
      const absoluteDelta = currentValue - legacyValue;
      const relativeDeltaPct =
        legacyValue === 0 ? (currentValue === 0 ? 0 : 100) : (absoluteDelta / legacyValue) * 100;

      return [
        field,
        {
          current: currentValue,
          legacy: legacyValue,
          absoluteDelta,
          relativeDeltaPct,
        },
      ];
    })
  );
  const maxAbsoluteDelta = Math.max(
    ...Object.values(fields).map((value) => Math.abs(value.absoluteDelta)),
    0
  );
  const maxRelativeDeltaPct = Math.max(
    ...Object.values(fields).map((value) => Math.abs(value.relativeDeltaPct)),
    0
  );

  return {
    fields,
    lengths: {
      dailyUsage: {
        current: current.dailyUsage.length,
        legacy: legacy.dailyUsage.length,
      },
      timeSeries: {
        hourly: {
          current: current.timeSeries.hourly.length,
          legacy: legacy.timeSeries.hourly.length,
        },
        daily: {
          current: current.timeSeries.daily.length,
          legacy: legacy.timeSeries.daily.length,
        },
        weekly: {
          current: current.timeSeries.weekly.length,
          legacy: legacy.timeSeries.weekly.length,
        },
        monthly: {
          current: current.timeSeries.monthly.length,
          legacy: legacy.timeSeries.monthly.length,
        },
      },
    },
    maxAbsoluteDelta,
    maxRelativeDeltaPct,
  };
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const daysParam = searchParams.get("days");
  const days = daysParam ? parseInt(daysParam, 10) : undefined;
  const provider = searchParams.get("provider") || undefined;
  const includeDebug = readBooleanParam(searchParams.get("debug"));
  const includeComparison = readBooleanParam(searchParams.get("compare"));
  const { analytics, debug } = await queryAnalytics(days, provider);
  const legacyAnalytics = includeComparison ? await getLegacyAnalytics(days, provider) : null;
  const responseBody =
    includeDebug || includeComparison
      ? {
          ...analytics,
          _debug: {
            ...debug,
            comparison: legacyAnalytics
              ? buildComparisonSummary(analytics, legacyAnalytics)
              : undefined,
          },
        }
      : analytics;
  const response = NextResponse.json(responseBody);
  response.headers.set("x-analytics-backend", debug.resolvedBackend);
  response.headers.set("x-analytics-requested-backend", debug.requestedBackend);
  response.headers.set("x-analytics-live-merge", debug.liveMergeApplied ? "1" : "0");
  if (debug.fallbackReason) {
    response.headers.set("x-analytics-fallback", "1");
  }
  return response;
}
