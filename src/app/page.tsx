"use client";

import { useState } from "react";
import { useAnalytics } from "@/hooks/use-conversations";
import { StatsCard } from "@/components/analytics/stats-card";
import {
  DailyUsageChart,
  ConversationsPerDayChart,
  ModelBreakdownChart,
  ToolUsageChart,
  SubagentTypeChart,
} from "@/components/analytics/charts";
import { CostBreakdownCard } from "@/components/analytics/cost-breakdown-card";
import { Skeleton } from "@/components/ui/skeleton";
import { DateRangePicker } from "@/components/ui/date-range-picker";
import { ProviderFilter, type Provider } from "@/components/ui/provider-filter";
import {
  MessageSquare,
  Wrench,
  Database,
  DatabaseZap,
} from "lucide-react";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function AnalyticsPage() {
  const [days, setDays] = useState<number | undefined>(7);
  const [provider, setProvider] = useState<Provider>("all");
  const { data: analytics, isLoading } = useAnalytics(days, provider);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-muted-foreground mt-1">
            Token usage, costs, and model statistics
          </p>
        </div>
        <div className="flex items-center gap-3">
          <DateRangePicker value={days} onChange={setDays} />
          <ProviderFilter value={provider} onChange={setProvider} />
        </div>
      </div>

      {isLoading ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
          <Skeleton className="h-64" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Skeleton className="h-80" />
            <Skeleton className="h-80" />
          </div>
        </>
      ) : analytics ? (
        <>
          {/* Top-level stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatsCard
              title="Conversations"
              value={analytics.totalConversations}
              icon={<MessageSquare className="h-4 w-4" />}
            />
            <StatsCard
              title="Input / Output Tokens"
              value={formatTokens(
                analytics.totalInputTokens + analytics.totalOutputTokens
              )}
              description={`${formatTokens(analytics.totalInputTokens)} in / ${formatTokens(analytics.totalOutputTokens)} out`}
              icon={<Database className="h-4 w-4" />}
            />
            <StatsCard
              title="Cache Tokens"
              value={formatTokens(
                analytics.totalCacheCreationTokens + analytics.totalCacheReadTokens
              )}
              description={`${formatTokens(analytics.totalCacheCreationTokens)} write / ${formatTokens(analytics.totalCacheReadTokens)} read`}
              icon={<DatabaseZap className="h-4 w-4" />}
            />
            <StatsCard
              title="Tool Calls"
              value={analytics.totalToolCalls.toLocaleString()}
              icon={<Wrench className="h-4 w-4" />}
            />
          </div>

          {/* Cost breakdown */}
          <CostBreakdownCard
            total={analytics.costBreakdown}
            byProvider={analytics.costBreakdownByProvider}
            byModel={analytics.costBreakdownByModel}
          />

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <DailyUsageChart data={analytics.dailyUsage} />
            <ConversationsPerDayChart data={analytics.dailyUsage} />
          </div>

          {Object.keys(analytics.toolBreakdownByProvider).length > 0 && (
            <ToolUsageChart data={analytics.toolBreakdownByProvider} />
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {Object.keys(analytics.subagentTypeBreakdownByProvider).length > 0 && (
              <SubagentTypeChart data={analytics.subagentTypeBreakdownByProvider} />
            )}
            {Object.keys(analytics.modelBreakdownByProvider).length > 0 && (
              <ModelBreakdownChart data={analytics.modelBreakdownByProvider} />
            )}
          </div>
        </>
      ) : (
        <p className="text-muted-foreground">Failed to load analytics</p>
      )}
    </div>
  );
}
