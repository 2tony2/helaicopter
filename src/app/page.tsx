"use client";

import { useEffect, useState } from "react";
import { useAnalytics, useSubscriptionSettings } from "@/hooks/use-conversations";
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
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  MessageSquare,
  Wrench,
  Database,
  DatabaseZap,
  CreditCard,
  Percent,
} from "lucide-react";
import type { SubscriptionSettings } from "@/lib/types";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function AnalyticsPage() {
  const [days, setDays] = useState<number | undefined>(7);
  const [provider, setProvider] = useState<Provider>("all");
  const [showSubscriptionPercent, setShowSubscriptionPercent] = useState(false);
  const { data: analytics, isLoading } = useAnalytics(days, provider);
  const {
    data: subscriptionSettings,
    mutate: mutateSubscriptionSettings,
  } = useSubscriptionSettings();
  const [draftSettings, setDraftSettings] = useState<SubscriptionSettings | null>(null);
  const [isSavingSubscriptions, setIsSavingSubscriptions] = useState(false);

  useEffect(() => {
    if (subscriptionSettings) {
      setDraftSettings(subscriptionSettings);
    }
  }, [subscriptionSettings]);

  async function saveSubscriptionSettings() {
    if (!draftSettings) {
      return;
    }

    setIsSavingSubscriptions(true);
    try {
      const response = await fetch("/api/subscription-settings", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(draftSettings),
      });
      const body = (await response.json()) as SubscriptionSettings;
      await mutateSubscriptionSettings(body, false);
    } finally {
      setIsSavingSubscriptions(false);
    }
  }

  const activeSubscriptionBudget = subscriptionSettings
    ? (provider === "all"
        ? (subscriptionSettings.claude.hasSubscription
            ? subscriptionSettings.claude.monthlyCost
            : 0) +
          (subscriptionSettings.codex.hasSubscription
            ? subscriptionSettings.codex.monthlyCost
            : 0)
        : subscriptionSettings[provider].hasSubscription
          ? subscriptionSettings[provider].monthlyCost
          : 0)
    : 0;

  const filteredProviderCost =
    analytics && provider !== "all"
      ? analytics.costBreakdownByProvider[provider]?.totalCost ?? 0
      : analytics?.costBreakdown.totalCost ?? 0;
  const subscriptionSpendPercent =
    activeSubscriptionBudget > 0
      ? (filteredProviderCost / activeSubscriptionBudget) * 100
      : 0;

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
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Skeleton className="h-80" />
            <Skeleton className="h-80" />
          </div>
        </>
      ) : analytics ? (
        <>
          {/* Top-level stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
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
            <StatsCard
              title="Subscription Spend"
              value={
                showSubscriptionPercent && activeSubscriptionBudget > 0
                  ? `${subscriptionSpendPercent.toFixed(1)}%`
                  : `$${filteredProviderCost.toFixed(2)}`
              }
              description={
                activeSubscriptionBudget > 0
                  ? `$${filteredProviderCost.toFixed(2)} of $${activeSubscriptionBudget.toFixed(2)}/month`
                  : "No active subscription budget"
              }
              icon={<CreditCard className="h-4 w-4" />}
            />
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <div>
                <CardTitle className="text-sm">Subscription Settings</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  Track monthly Claude and ChatGPT subscription costs alongside API spend.
                </p>
              </div>
              <Button
                type="button"
                variant={showSubscriptionPercent ? "default" : "outline"}
                onClick={() => setShowSubscriptionPercent((current) => !current)}
              >
                <Percent className="h-4 w-4" />
                {showSubscriptionPercent ? "Showing % of subscriptions" : "Show % of subscriptions"}
              </Button>
            </CardHeader>
            <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
              {(["claude", "codex"] as const).map((providerKey) => (
                <div key={providerKey} className="rounded-lg border p-4 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">
                      {providerKey === "claude" ? "Claude" : "ChatGPT / Codex"}
                    </div>
                    <label className="flex items-center gap-2 text-sm text-muted-foreground">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        checked={draftSettings?.[providerKey].hasSubscription ?? false}
                        onChange={(event) =>
                          setDraftSettings((current) =>
                            current
                              ? {
                                  ...current,
                                  [providerKey]: {
                                    ...current[providerKey],
                                    hasSubscription: event.target.checked,
                                  },
                                }
                              : current
                          )
                        }
                      />
                      Has subscription
                    </label>
                  </div>
                  <div className="space-y-2">
                    <div className="text-sm text-muted-foreground">Monthly cost</div>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={draftSettings?.[providerKey].monthlyCost ?? 200}
                      onChange={(event) =>
                        setDraftSettings((current) =>
                          current
                            ? {
                                ...current,
                                [providerKey]: {
                                  ...current[providerKey],
                                  monthlyCost: Number(event.target.value || 0),
                                },
                              }
                            : current
                        )
                      }
                    />
                  </div>
                </div>
              ))}
              <div className="flex items-end">
                <Button
                  type="button"
                  onClick={() => void saveSubscriptionSettings()}
                  disabled={!draftSettings || isSavingSubscriptions}
                >
                  Save Settings
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Cost breakdown */}
          <CostBreakdownCard
            total={analytics.costBreakdown}
            byProvider={analytics.costBreakdownByProvider}
            byModel={analytics.costBreakdownByModel}
            subscriptionSettings={
              subscriptionSettings ?? {
                claude: {
                  provider: "claude",
                  hasSubscription: true,
                  monthlyCost: 200,
                  updatedAt: new Date().toISOString(),
                },
                codex: {
                  provider: "codex",
                  hasSubscription: true,
                  monthlyCost: 200,
                  updatedAt: new Date().toISOString(),
                },
              }
            }
            showSubscriptionPercent={showSubscriptionPercent}
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
