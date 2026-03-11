"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnalyticsRateValue, AnalyticsRates } from "@/lib/types";
import { formatCost } from "@/lib/pricing";

function formatTokens(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 10_000_000) return `${(value / 1_000_000).toFixed(0)}M`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 10_000) return `${(value / 1_000).toFixed(0)}K`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  if (value >= 100) return value.toFixed(0);
  if (value >= 1) return value.toFixed(1);
  if (value === 0) return "0";
  return value.toFixed(1);
}

function formatActivity(value: number): string {
  if (value >= 10_000) return `${(value / 1_000).toFixed(1)}K`;
  if (value >= 1_000) return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (value >= 100) return value.toFixed(0);
  if (value >= 1) return value.toFixed(1);
  if (value === 0) return "0";
  return value.toFixed(1);
}

const PERIOD_HEADERS = ["/ Hour", "/ Day", "/ Week", "/ Month"] as const;

function RateHeader({ firstCol }: { firstCol: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,1fr))] gap-2 border-b pb-2 text-xs uppercase tracking-wide text-muted-foreground">
      <div>{firstCol}</div>
      {PERIOD_HEADERS.map((h) => (
        <div key={h} className="text-right">{h}</div>
      ))}
    </div>
  );
}

function RateRow({
  label,
  value,
  format,
  highlight,
  color,
}: {
  label: string;
  value: AnalyticsRateValue;
  format: (input: number) => string;
  highlight?: boolean;
  color?: string;
}) {
  const cls = highlight ? "font-semibold" : "";
  return (
    <div className={`grid grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,1fr))] gap-2 items-center py-2 ${cls}`}>
      <div className="text-sm font-medium truncate flex items-center gap-2">
        {color && <span className="inline-block h-2 w-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />}
        {label}
      </div>
      <div className="text-right font-mono text-sm tabular-nums" style={color ? { color } : undefined}>{format(value.perHour)}</div>
      <div className="text-right font-mono text-sm tabular-nums" style={color ? { color } : undefined}>{format(value.perDay)}</div>
      <div className="text-right font-mono text-sm tabular-nums" style={color ? { color } : undefined}>{format(value.perWeek)}</div>
      <div className="text-right font-mono text-sm tabular-nums" style={color ? { color } : undefined}>{format(value.perMonth)}</div>
    </div>
  );
}

const SPEND_PERIODS = [
  { key: "perHour", label: "Per hour" },
  { key: "perDay", label: "Per day" },
  { key: "perWeek", label: "Per week" },
  { key: "perMonth", label: "Per month" },
] as const;

export function SpendRateCard({ rates }: { rates: AnalyticsRates }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Average Spend Rate</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {SPEND_PERIODS.map(({ key, label }) => (
            <div key={key} className="flex items-baseline justify-between rounded-md border px-3 py-2.5">
              <span className="text-xs text-muted-foreground">{label}</span>
              <span className="font-mono text-lg font-semibold tabular-nums" style={{ color: "#059669" }}>
                {formatCost(rates.spend[key])}
              </span>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Normalized averages over the selected analytics range.
        </p>
      </CardContent>
    </Card>
  );
}

export function TokenRateCard({ rates }: { rates: AnalyticsRates }) {
  const rows = [
    { label: "Input", value: rates.inputTokens, color: "#2563eb" },
    { label: "Output", value: rates.outputTokens, color: "#059669" },
    { label: "Cache write", value: rates.cacheWriteTokens, color: "#d97706" },
    { label: "Cache read", value: rates.cacheReadTokens, color: "#7c3aed" },
    { label: "Reasoning", value: rates.reasoningTokens, color: "#dc2626" },
    { label: "Total", value: rates.totalTokens, highlight: true },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Token Rate Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <RateHeader firstCol="Token type" />
        <div className="divide-y">
          {rows.map((row) => (
            <RateRow
              key={row.label}
              label={row.label}
              value={row.value}
              format={formatTokens}
              highlight={row.highlight}
              color={row.color}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function ActivityRateCard({ rates }: { rates: AnalyticsRates }) {
  const rows = [
    { label: "Conversations", value: rates.conversations, color: "#64748b" },
    { label: "Tool calls", value: rates.toolCalls, color: "#7c3aed" },
    { label: "Failed tool calls", value: rates.failedToolCalls, color: "#dc2626" },
    { label: "Sub-agents", value: rates.subagents, color: "#2563eb" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Activity Rate Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <RateHeader firstCol="Activity" />
        <div className="divide-y">
          {rows.map((row) => (
            <RateRow
              key={row.label}
              label={row.label}
              value={row.value}
              format={formatActivity}
              color={row.color}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
