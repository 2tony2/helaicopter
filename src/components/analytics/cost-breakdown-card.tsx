"use client";

import { useState } from "react";
import {
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  BookOpen,
  DatabaseZap,
} from "lucide-react";
import { formatCost } from "@/lib/pricing";
import type {
  AnalyticsCostBreakdown,
  AnalyticsCostBreakdownMap,
  SubscriptionSettings,
  SupportedProvider,
} from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { isOpenAIModel } from "@/lib/utils";

function pct(part: number, total: number): string {
  if (total === 0) return "0%";
  return `${((part / total) * 100).toFixed(1)}%`;
}

type BreakdownOption = {
  key: string;
  label: string;
  breakdown: AnalyticsCostBreakdown;
};

function modelLabel(model: string): string {
  return model === "unknown" ? "Model: Unknown" : `Model: ${model}`;
}

function isOpenAISelection(selectedKey: string): boolean {
  if (selectedKey === "provider:codex") return true;
  if (!selectedKey.startsWith("model:")) return false;
  return isOpenAIModel(selectedKey.slice("model:".length));
}

function getBudgetForSelection(
  selectedKey: string,
  settings: SubscriptionSettings
): { budget: number; label: string } | null {
  const providerFromKey = selectedKey.startsWith("provider:")
    ? (selectedKey.slice("provider:".length) as SupportedProvider)
    : null;

  if (providerFromKey) {
    const setting = settings[providerFromKey];
    if (!setting.hasSubscription || setting.monthlyCost <= 0) {
      return null;
    }

    return {
      budget: setting.monthlyCost,
      label: `${providerFromKey === "claude" ? "Claude" : "Codex"} subscription`,
    };
  }

  const providers = (["claude", "codex"] as const).filter(
    (provider) => settings[provider].hasSubscription && settings[provider].monthlyCost > 0
  );

  if (providers.length === 0) {
    return null;
  }

  return {
    budget: providers.reduce((sum, provider) => sum + settings[provider].monthlyCost, 0),
    label:
      providers.length === 1
        ? `${providers[0] === "claude" ? "Claude" : "Codex"} subscription`
        : "combined subscriptions",
  };
}

export function CostBreakdownCard({
  total,
  byProvider,
  byModel,
  subscriptionSettings,
  showSubscriptionPercent,
}: {
  total: AnalyticsCostBreakdown;
  byProvider: AnalyticsCostBreakdownMap;
  byModel: AnalyticsCostBreakdownMap;
  subscriptionSettings: SubscriptionSettings;
  showSubscriptionPercent: boolean;
}) {
  const options: BreakdownOption[] = [
    { key: "total", label: "Total", breakdown: total },
    ...Object.entries(byProvider)
      .filter(([, breakdown]) => breakdown.totalCost > 0)
      .sort((a, b) => b[1].totalCost - a[1].totalCost)
      .map(([providerKey, breakdown]) => ({
        key: `provider:${providerKey}`,
        label: `Provider: ${providerKey === "claude" ? "Claude" : "Codex"}`,
        breakdown,
      })),
    ...Object.entries(byModel)
      .filter(([, breakdown]) => breakdown.totalCost > 0)
      .sort((a, b) => b[1].totalCost - a[1].totalCost)
      .map(([model, breakdown]) => ({
        key: `model:${model}`,
        label: modelLabel(model),
        breakdown,
      })),
  ];

  const [selectedKey, setSelectedKey] = useState(options[0]?.key || "total");
  const selected =
    options.find((option) => option.key === selectedKey) || options[0];
  const cb = selected.breakdown;
  const openAISelection = isOpenAISelection(selected.key);
  const budgetInfo = getBudgetForSelection(selected.key, subscriptionSettings);
  const subscriptionPercentLabel =
    budgetInfo && budgetInfo.budget > 0
      ? pct(cb.totalCost, budgetInfo.budget)
      : null;
  const rows = [
    {
      label: "Input tokens",
      cost: cb.inputCost,
      icon: ArrowDownToLine,
      colorClass: "text-blue-500",
    },
    {
      label: "Output tokens",
      cost: cb.outputCost,
      icon: ArrowUpFromLine,
      colorClass: "text-green-500",
    },
    {
      label: openAISelection ? "Cached input" : "Cache read",
      cost: cb.cacheReadCost,
      icon: BookOpen,
      colorClass: "text-purple-500",
    },
  ];
  if (!openAISelection) {
    rows.splice(2, 0, {
      label: "Cache write (5m)",
      cost: cb.cacheWriteCost,
      icon: DatabaseZap,
      colorClass: "text-yellow-500",
    });
  }
  const hasLongContext = cb.longContextPremium > 0;

  return (
    <Card>
      <CardHeader className="pb-3 flex flex-row items-center justify-between gap-3">
        <CardTitle className="text-sm">Estimated Cost Breakdown</CardTitle>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          value={selected.key}
          onChange={(e) => setSelectedKey(e.target.value)}
        >
          {options.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center gap-3">
            <row.icon className={`h-4 w-4 shrink-0 ${row.colorClass}`} />
            <span className="text-sm flex-1">{row.label}</span>
            <span className="text-sm font-mono w-20 text-right">
              {formatCost(row.cost)}
            </span>
            <span className="text-xs text-muted-foreground w-12 text-right">
              {showSubscriptionPercent && budgetInfo
                ? pct(row.cost, budgetInfo.budget)
                : pct(row.cost, cb.totalCost)}
            </span>
          </div>
        ))}

        {openAISelection && (
          <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            OpenAI/Codex does not bill cache writes separately. Cache fills are included in input cost, and only cached input is discounted separately.
          </div>
        )}

        {hasLongContext && (
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
            <span className="text-sm flex-1">
              Long context premium
              <span className="text-xs text-muted-foreground ml-1">
                ({cb.longContextConversations} convos &gt;200K)
              </span>
            </span>
            <span className="text-sm font-mono w-20 text-right text-amber-600 dark:text-amber-400">
              {formatCost(cb.longContextPremium)}
            </span>
            <span className="text-xs text-muted-foreground w-12 text-right">
              {showSubscriptionPercent && budgetInfo
                ? pct(cb.longContextPremium, budgetInfo.budget)
                : pct(cb.longContextPremium, cb.totalCost)}
            </span>
          </div>
        )}

        <div className="border-t pt-2 mt-2 flex items-center gap-3">
          <div className="h-4 w-4 shrink-0" />
          <span className="text-sm flex-1 font-semibold">Total</span>
          <span className="text-sm font-mono font-semibold w-20 text-right">
            {formatCost(cb.totalCost)}
          </span>
          <span className="text-xs text-muted-foreground w-12 text-right">
            {showSubscriptionPercent && subscriptionPercentLabel
              ? subscriptionPercentLabel
              : "100%"}
          </span>
        </div>

        {showSubscriptionPercent && (
          <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            {budgetInfo ? (
              <>
                Current spend is <span className="font-medium text-foreground">{subscriptionPercentLabel}</span> of the{" "}
                <span className="font-medium text-foreground">
                  {budgetInfo.label}
                </span>{" "}
                budget ({formatCost(budgetInfo.budget)}/month).
              </>
            ) : (
              <>
                No active subscription budget applies to this selection. Enable a subscription and monthly amount to see percentage spend.
              </>
            )}
          </div>
        )}

        <div className="flex h-3 rounded-full overflow-hidden mt-3">
          {cb.inputCost > 0 && (
            <div
              className="bg-blue-500"
              style={{ width: pct(cb.inputCost, cb.totalCost) }}
              title={`Input: ${formatCost(cb.inputCost)}`}
            />
          )}
          {cb.outputCost > 0 && (
            <div
              className="bg-green-500"
              style={{ width: pct(cb.outputCost, cb.totalCost) }}
              title={`Output: ${formatCost(cb.outputCost)}`}
            />
          )}
          {!openAISelection && cb.cacheWriteCost > 0 && (
            <div
              className="bg-yellow-500"
              style={{ width: pct(cb.cacheWriteCost, cb.totalCost) }}
              title={`Cache write: ${formatCost(cb.cacheWriteCost)}`}
            />
          )}
          {cb.cacheReadCost > 0 && (
            <div
              className="bg-purple-500"
              style={{ width: pct(cb.cacheReadCost, cb.totalCost) }}
              title={`Cache read: ${formatCost(cb.cacheReadCost)}`}
            />
          )}
          {hasLongContext && (
            <div
              className="bg-amber-500"
              style={{ width: pct(cb.longContextPremium, cb.totalCost) }}
              title={`Long context premium: ${formatCost(cb.longContextPremium)}`}
            />
          )}
        </div>
        <div className="flex gap-3 text-xs text-muted-foreground flex-wrap mt-1">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-blue-500" />Input</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-green-500" />Output</span>
          {!openAISelection && (
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-yellow-500" />Cache write</span>
          )}
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-purple-500" />{openAISelection ? "Cached input" : "Cache read"}</span>
          {hasLongContext && (
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-amber-500" />Long ctx premium</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
