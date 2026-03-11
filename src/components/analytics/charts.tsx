"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCost } from "@/lib/pricing";
import type {
  DailyUsage,
  ProviderBreakdown,
  AnalyticsTimeSeriesPoint,
} from "@/lib/types";

function formatTokenAxis(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return String(value);
}

function providerBreakdownToChartData(data: Record<string, ProviderBreakdown>) {
  return Object.entries(data)
    .map(([name, counts]) => ({
      name: name.replace(/^mcp__[^_]+__/, "mcp:").replace("claude-", ""),
      claude: counts.claude,
      codex: counts.codex,
      total: counts.claude + counts.codex,
    }))
    .sort((a, b) => b.total - a.total);
}

export function DailyUsageChart({ data }: { data: DailyUsage[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Daily Token Usage by Provider</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="date"
              className="text-xs"
              tickFormatter={(v) => v.slice(5)}
            />
            <YAxis
              className="text-xs"
              tickFormatter={(v) =>
                v >= 1_000_000
                  ? `${(v / 1_000_000).toFixed(0)}M`
                  : `${(v / 1_000).toFixed(0)}K`
              }
            />
            <Tooltip
              formatter={(value) => typeof value === "number" ? value.toLocaleString() : String(value)}
              labelStyle={{ color: "var(--foreground)" }}
              contentStyle={{
                backgroundColor: "var(--background)",
                border: "1px solid var(--border)",
              }}
            />
            <Bar dataKey="claudeInputTokens" fill="#2563eb" name="Claude input" stackId="a" />
            <Bar dataKey="claudeOutputTokens" fill="#059669" name="Claude output" stackId="a" />
            <Bar dataKey="claudeCacheWriteTokens" fill="#d97706" name="Claude cache write" stackId="a" />
            <Bar dataKey="claudeCacheReadTokens" fill="#7c3aed" name="Claude cache read" stackId="a" />
            <Bar dataKey="codexInputTokens" fill="#93c5fd" name="Codex input" stackId="a" />
            <Bar dataKey="codexOutputTokens" fill="#6ee7b7" name="Codex output" stackId="a" />
            <Bar dataKey="codexCacheWriteTokens" fill="#fcd34d" name="Codex cache write" stackId="a" />
            <Bar dataKey="codexCacheReadTokens" fill="#c4b5fd" name="Codex cache read" stackId="a" />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function ConversationsPerDayChart({ data }: { data: DailyUsage[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Conversations & Sub-agents by Provider</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="date"
              className="text-xs"
              tickFormatter={(v) => v.slice(5)}
            />
            <YAxis className="text-xs" />
            <Tooltip
              labelStyle={{ color: "var(--foreground)" }}
              contentStyle={{
                backgroundColor: "var(--background)",
                border: "1px solid var(--border)",
              }}
            />
            <Line
              type="monotone"
              dataKey="claudeConversations"
              stroke="#2563eb"
              strokeWidth={2}
              dot={false}
              name="Claude conversations"
            />
            <Line
              type="monotone"
              dataKey="codexConversations"
              stroke="#93c5fd"
              strokeWidth={2}
              dot={false}
              name="Codex conversations"
            />
            <Line
              type="monotone"
              dataKey="claudeSubagents"
              stroke="#d97706"
              strokeWidth={2}
              dot={false}
              name="Claude sub-agents"
            />
            <Line
              type="monotone"
              dataKey="codexSubagents"
              stroke="#fcd34d"
              strokeWidth={2}
              dot={false}
              name="Codex sub-agents"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function SubagentTypeChart({
  data,
}: {
  data: Record<string, ProviderBreakdown>;
}) {
  const chartData = providerBreakdownToChartData(data);
  const total = chartData.reduce((s, d) => s + d.total, 0);

  if (chartData.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">
          Sub-agent Types ({total} total)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={Math.max(200, chartData.length * 40 + 60)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 120 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
            <XAxis type="number" className="text-xs" />
            <YAxis
              type="category"
              dataKey="name"
              className="text-xs"
              width={115}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              formatter={(value) =>
                typeof value === "number" ? value.toLocaleString() : String(value)
              }
              labelStyle={{ color: "var(--foreground)" }}
              contentStyle={{
                backgroundColor: "var(--background)",
                border: "1px solid var(--border)",
              }}
            />
            <Bar dataKey="claude" name="Claude" stackId="a" fill="#2563eb" radius={[0, 0, 0, 0]} />
            <Bar dataKey="codex" name="Codex" stackId="a" fill="#93c5fd" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function ToolUsageChart({
  data,
}: {
  data: Record<string, ProviderBreakdown>;
}) {
  const chartData = providerBreakdownToChartData(data);

  const barHeight = 32;
  const chartHeight = Math.max(300, chartData.length * barHeight + 60);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Tool Usage (sorted by frequency)</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 120 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
            <XAxis
              type="number"
              className="text-xs"
              tickFormatter={(v) =>
                v >= 1000 ? `${(v / 1000).toFixed(1)}K` : String(v)
              }
            />
            <YAxis
              type="category"
              dataKey="name"
              className="text-xs"
              width={115}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              formatter={(value) =>
                typeof value === "number"
                  ? value.toLocaleString()
                  : String(value)
              }
              labelStyle={{ color: "var(--foreground)" }}
              contentStyle={{
                backgroundColor: "var(--background)",
                border: "1px solid var(--border)",
              }}
            />
            <Bar dataKey="claude" fill="#2563eb" name="Claude" stackId="a" radius={[0, 0, 0, 0]} />
            <Bar dataKey="codex" fill="#93c5fd" name="Codex" stackId="a" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function ModelBreakdownChart({
  data,
}: {
  data: Record<string, ProviderBreakdown>;
}) {
  const chartData = providerBreakdownToChartData(data);
  const chartHeight = Math.max(260, chartData.length * 32 + 60);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Model Usage by Provider</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 120 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
            <XAxis type="number" className="text-xs" />
            <YAxis
              type="category"
              dataKey="name"
              className="text-xs"
              width={115}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              formatter={(value) =>
                typeof value === "number" ? value.toLocaleString() : String(value)
              }
              labelStyle={{ color: "var(--foreground)" }}
              contentStyle={{
                backgroundColor: "var(--background)",
                border: "1px solid var(--border)",
              }}
            />
            <Bar dataKey="claude" fill="#2563eb" name="Claude" stackId="a" radius={[0, 0, 0, 0]} />
            <Bar dataKey="codex" fill="#93c5fd" name="Codex" stackId="a" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function SpendTrendChart({
  data,
  granularityLabel,
}: {
  data: AnalyticsTimeSeriesPoint[];
  granularityLabel: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Spend Trend by {granularityLabel}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="label" className="text-xs" minTickGap={24} />
            <YAxis
              className="text-xs"
              tickFormatter={(value) => formatCost(value)}
            />
            <Tooltip
              formatter={(value) =>
                typeof value === "number" ? formatCost(value) : String(value)
              }
              labelStyle={{ color: "var(--foreground)" }}
              contentStyle={{
                backgroundColor: "var(--background)",
                border: "1px solid var(--border)",
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="estimatedCost"
              stroke="#64748b"
              strokeWidth={2.5}
              dot={false}
              name="Total spend"
            />
            <Line
              type="monotone"
              dataKey="claudeEstimatedCost"
              stroke="#2563eb"
              strokeWidth={2}
              dot={false}
              name="Claude spend"
            />
            <Line
              type="monotone"
              dataKey="codexEstimatedCost"
              stroke="#059669"
              strokeWidth={2}
              dot={false}
              name="Codex spend"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function TokenMixChart({
  data,
  granularityLabel,
}: {
  data: AnalyticsTimeSeriesPoint[];
  granularityLabel: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Token Mix by {granularityLabel}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="label" className="text-xs" minTickGap={24} />
            <YAxis className="text-xs" tickFormatter={formatTokenAxis} />
            <Tooltip
              formatter={(value) =>
                typeof value === "number" ? value.toLocaleString() : String(value)
              }
              labelStyle={{ color: "var(--foreground)" }}
              contentStyle={{
                backgroundColor: "var(--background)",
                border: "1px solid var(--border)",
              }}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="inputTokens"
              stackId="tokens"
              stroke="#2563eb"
              fill="#2563eb"
              fillOpacity={0.6}
              name="Input"
            />
            <Area
              type="monotone"
              dataKey="outputTokens"
              stackId="tokens"
              stroke="#059669"
              fill="#059669"
              fillOpacity={0.55}
              name="Output"
            />
            <Area
              type="monotone"
              dataKey="cacheWriteTokens"
              stackId="tokens"
              stroke="#d97706"
              fill="#d97706"
              fillOpacity={0.5}
              name="Cache write"
            />
            <Area
              type="monotone"
              dataKey="cacheReadTokens"
              stackId="tokens"
              stroke="#7c3aed"
              fill="#7c3aed"
              fillOpacity={0.45}
              name="Cache read"
            />
            <Area
              type="monotone"
              dataKey="reasoningTokens"
              stackId="tokens"
              stroke="#dc2626"
              fill="#dc2626"
              fillOpacity={0.4}
              name="Reasoning"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function ActivityTrendChart({
  data,
  granularityLabel,
}: {
  data: AnalyticsTimeSeriesPoint[];
  granularityLabel: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Conversation Activity by {granularityLabel}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="label" className="text-xs" minTickGap={24} />
            <YAxis className="text-xs" />
            <Tooltip
              formatter={(value) =>
                typeof value === "number" ? value.toLocaleString() : String(value)
              }
              labelStyle={{ color: "var(--foreground)" }}
              contentStyle={{
                backgroundColor: "var(--background)",
                border: "1px solid var(--border)",
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="conversations"
              stroke="#2563eb"
              strokeWidth={2}
              dot={false}
              name="Conversations"
            />
            <Line
              type="monotone"
              dataKey="toolCalls"
              stroke="#d97706"
              strokeWidth={2}
              dot={false}
              name="Tool calls"
            />
            <Line
              type="monotone"
              dataKey="subagents"
              stroke="#7c3aed"
              strokeWidth={2}
              dot={false}
              name="Sub-agents"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
