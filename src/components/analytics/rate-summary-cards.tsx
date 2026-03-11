"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnalyticsRateValue, AnalyticsRates } from "@/lib/types";
import { formatCost } from "@/lib/pricing";

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(value >= 100 ? 0 : 1);
}

function RateRow({
  label,
  value,
  format,
}: {
  label: string;
  value: AnalyticsRateValue;
  format: (input: number) => string;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,1fr))] gap-3 items-center py-2">
      <div className="text-sm font-medium">{label}</div>
      <div className="text-right font-mono text-sm">{format(value.perHour)}</div>
      <div className="text-right font-mono text-sm">{format(value.perDay)}</div>
      <div className="text-right font-mono text-sm">{format(value.perWeek)}</div>
      <div className="text-right font-mono text-sm">{format(value.perMonth)}</div>
    </div>
  );
}

export function SpendRateCard({ rates }: { rates: AnalyticsRates }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Average Spend Rate</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-4 gap-3 text-xs uppercase tracking-wide text-muted-foreground">
          <div className="text-left">/ Hour</div>
          <div className="text-right">/ Day</div>
          <div className="text-right">/ Week</div>
          <div className="text-right">/ Month</div>
        </div>
        <div className="grid grid-cols-4 gap-3">
          <div className="rounded-lg border p-3">
            <div className="text-xs text-muted-foreground">Spend / hour</div>
            <div className="mt-1 font-mono text-xl font-semibold">
              {formatCost(rates.spend.perHour)}
            </div>
          </div>
          <div className="rounded-lg border p-3">
            <div className="text-xs text-muted-foreground">Spend / day</div>
            <div className="mt-1 font-mono text-xl font-semibold">
              {formatCost(rates.spend.perDay)}
            </div>
          </div>
          <div className="rounded-lg border p-3">
            <div className="text-xs text-muted-foreground">Spend / week</div>
            <div className="mt-1 font-mono text-xl font-semibold">
              {formatCost(rates.spend.perWeek)}
            </div>
          </div>
          <div className="rounded-lg border p-3">
            <div className="text-xs text-muted-foreground">Spend / month</div>
            <div className="mt-1 font-mono text-xl font-semibold">
              {formatCost(rates.spend.perMonth)}
            </div>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          These are normalized averages over the currently selected analytics range.
        </p>
      </CardContent>
    </Card>
  );
}

export function TokenRateCard({ rates }: { rates: AnalyticsRates }) {
  const rows = [
    { label: "Input", value: rates.inputTokens },
    { label: "Output", value: rates.outputTokens },
    { label: "Cache write", value: rates.cacheWriteTokens },
    { label: "Cache read", value: rates.cacheReadTokens },
    { label: "Reasoning", value: rates.reasoningTokens },
    { label: "Total", value: rates.totalTokens },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Token Rate Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,1fr))] gap-3 border-b pb-2 text-xs uppercase tracking-wide text-muted-foreground">
          <div>Token type</div>
          <div className="text-right">/ Hour</div>
          <div className="text-right">/ Day</div>
          <div className="text-right">/ Week</div>
          <div className="text-right">/ Month</div>
        </div>
        <div className="divide-y">
          {rows.map((row) => (
            <RateRow
              key={row.label}
              label={row.label}
              value={row.value}
              format={formatTokens}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function ActivityRateCard({ rates }: { rates: AnalyticsRates }) {
  const rows = [
    { label: "Conversations", value: rates.conversations },
    { label: "Tool calls", value: rates.toolCalls },
    { label: "Sub-agents", value: rates.subagents },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Activity Rate Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,1fr))] gap-3 border-b pb-2 text-xs uppercase tracking-wide text-muted-foreground">
          <div>Activity</div>
          <div className="text-right">/ Hour</div>
          <div className="text-right">/ Day</div>
          <div className="text-right">/ Week</div>
          <div className="text-right">/ Month</div>
        </div>
        <div className="divide-y">
          {rows.map((row) => (
            <RateRow
              key={row.label}
              label={row.label}
              value={row.value}
              format={(value) => value.toFixed(value >= 100 ? 0 : 1)}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
