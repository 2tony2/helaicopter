"use client";

import { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageCard } from "./message-card";
import { cn } from "@/lib/utils";
import { ChevronDown, X } from "lucide-react";
import { calculateCost, formatCost } from "@/lib/pricing";
import type {
  ContextAnalytics,
  ContextBucket,
  ContextStep,
  ContextWindowStats,
  TokenUsage,
  ProcessedMessage,
} from "@/lib/types";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function pct(part: number, total: number): string {
  if (total === 0) return "0%";
  return `${((part / total) * 100).toFixed(1)}%`;
}

type Category = ContextBucket["category"];

const CATEGORY_COLORS: Record<string, string> = {
  tool: "#3b82f6",
  mcp: "#8b5cf6",
  subagent: "#f59e0b",
  thinking: "#ec4899",
  conversation: "#10b981",
};

const CATEGORY_LABELS: Record<string, string> = {
  tool: "Built-in tools",
  mcp: "MCP tools",
  subagent: "Sub-agents",
  thinking: "Thinking",
  conversation: "Conversation",
};

function CategorySummary({
  analytics,
  totalUsage,
  activeFilter,
  onFilterChange,
  model,
}: {
  analytics: ContextAnalytics;
  totalUsage: TokenUsage;
  activeFilter: Category | null;
  onFilterChange: (cat: Category | null) => void;
  model?: string;
}) {
  const grandTotal =
    (totalUsage.input_tokens || 0) +
    (totalUsage.output_tokens || 0) +
    (totalUsage.cache_creation_input_tokens || 0) +
    (totalUsage.cache_read_input_tokens || 0);

  const totalCost = calculateCost(totalUsage, model).totalCost;

  const categoryMap = new Map<string, { tokens: number; calls: number; cost: number }>();
  for (const b of analytics.buckets) {
    const existing = categoryMap.get(b.category) || { tokens: 0, calls: 0, cost: 0 };
    existing.tokens += b.totalTokens;
    existing.calls += b.calls;
    existing.cost += calculateCost(
      { inputTokens: b.inputTokens, outputTokens: b.outputTokens, cacheWriteTokens: b.cacheWriteTokens, cacheReadTokens: b.cacheReadTokens },
      model
    ).totalCost;
    categoryMap.set(b.category, existing);
  }

  const categories = Array.from(categoryMap.entries())
    .map(([cat, v]) => ({ cat: cat as Category, ...v }))
    .sort((a, b) => b.tokens - a.tokens);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Context by Category</CardTitle>
          {activeFilter && (
            <button
              onClick={() => onFilterChange(null)}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              Clear filter <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-1">
        {categories.map(({ cat, tokens, calls, cost }) => (
          <button
            key={cat}
            onClick={() =>
              onFilterChange(activeFilter === cat ? null : cat)
            }
            className={cn(
              "flex items-center gap-3 w-full rounded-md px-2 py-1.5 transition-colors text-left",
              activeFilter === cat
                ? "bg-accent"
                : activeFilter
                  ? "opacity-40 hover:opacity-70"
                  : "hover:bg-accent/50"
            )}
          >
            <div
              className="w-3 h-3 rounded-sm shrink-0"
              style={{
                backgroundColor: CATEGORY_COLORS[cat] || "#6b7280",
              }}
            />
            <span className="text-sm flex-1">
              {CATEGORY_LABELS[cat] || cat}
            </span>
            <span className="text-xs text-muted-foreground">
              {calls}
            </span>
            <span className="text-sm font-mono font-medium w-16 text-right">
              {formatTokens(tokens)}
            </span>
            <span className="text-xs font-mono text-amber-600 dark:text-amber-400 w-14 text-right">
              {formatCost(cost)}
            </span>
            <span className="text-xs text-muted-foreground w-10 text-right">
              {pct(tokens, grandTotal)}
            </span>
          </button>
        ))}
        <div className="border-t pt-2 mt-2 flex items-center gap-3 px-2">
          <div className="w-3 h-3 shrink-0" />
          <span className="text-sm flex-1 font-medium">Total</span>
          <span className="text-sm font-mono font-medium w-16 text-right">
            {formatTokens(grandTotal)}
          </span>
          <span className="text-xs font-mono font-medium text-amber-600 dark:text-amber-400 w-14 text-right">
            {formatCost(totalCost)}
          </span>
          <span className="text-xs text-muted-foreground w-10 text-right">
            100%
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function ToolBreakdownChart({
  buckets,
  activeFilter,
}: {
  buckets: ContextBucket[];
  activeFilter: Category | null;
}) {
  const filtered = activeFilter
    ? buckets.filter((b) => b.category === activeFilter)
    : buckets;
  const data = filtered.slice(0, 25).map((b) => ({
    name: b.label.replace(/^mcp__[^_]+__/, "mcp:"),
    total: b.totalTokens,
    input: b.inputTokens,
    output: b.outputTokens,
    cacheWrite: b.cacheWriteTokens,
    cacheRead: b.cacheReadTokens,
    calls: b.calls,
    category: b.category,
  }));

  if (data.length === 0) return null;

  const barHeight = 28;
  const height = Math.max(200, data.length * barHeight + 60);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">
          Context by Tool / Source
          {activeFilter && (
            <Badge variant="secondary" className="ml-2 text-xs">
              {CATEGORY_LABELS[activeFilter]}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} layout="vertical" margin={{ left: 130 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              className="stroke-muted"
              horizontal={false}
            />
            <XAxis
              type="number"
              className="text-xs"
              tickFormatter={(v) =>
                v >= 1_000_000
                  ? `${(v / 1_000_000).toFixed(0)}M`
                  : v >= 1_000
                    ? `${(v / 1_000).toFixed(0)}K`
                    : String(v)
              }
            />
            <YAxis
              type="category"
              dataKey="name"
              className="text-xs"
              width={125}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              formatter={(value, name) => [
                typeof value === "number"
                  ? value.toLocaleString()
                  : String(value),
                String(name),
              ]}
              labelStyle={{ color: "var(--foreground)" }}
              contentStyle={{
                backgroundColor: "var(--background)",
                border: "1px solid var(--border)",
                fontSize: 12,
              }}
            />
            <Bar dataKey="input" stackId="a" fill="#3b82f6" name="Input" />
            <Bar
              dataKey="output"
              stackId="a"
              fill="#10b981"
              name="Output"
            />
            <Bar
              dataKey="cacheWrite"
              stackId="a"
              fill="#f59e0b"
              name="Cache write"
            />
            <Bar
              dataKey="cacheRead"
              stackId="a"
              fill="#8b5cf6"
              name="Cache read"
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

function StepDetail({
  step,
  message,
  onClose,
  model,
}: {
  step: ContextStep;
  message: ProcessedMessage | undefined;
  onClose: () => void;
  model?: string;
}) {
  const cost = calculateCost(
    { inputTokens: step.inputTokens, outputTokens: step.outputTokens, cacheWriteTokens: step.cacheWriteTokens, cacheReadTokens: step.cacheReadTokens },
    model
  );

  return (
    <Card className="border-primary/30 bg-accent/20">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-sm">
              Step #{step.index + 1}: {step.label}
            </CardTitle>
            <Badge
              variant="secondary"
              className="text-xs"
              style={{
                borderColor: CATEGORY_COLORS[step.category],
                color: CATEGORY_COLORS[step.category],
              }}
            >
              {CATEGORY_LABELS[step.category]}
            </Badge>
            <Badge variant="outline" className="text-xs font-mono text-amber-600 dark:text-amber-400">
              {formatCost(cost.totalCost)}
            </Badge>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Token + cost breakdown */}
        <div className="grid grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-xs text-muted-foreground">Input</div>
            <div className="font-mono text-blue-500">
              {step.inputTokens.toLocaleString()}
            </div>
            <div className="font-mono text-xs text-muted-foreground">{formatCost(cost.inputCost)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Output</div>
            <div className="font-mono text-green-500">
              {step.outputTokens.toLocaleString()}
            </div>
            <div className="font-mono text-xs text-muted-foreground">{formatCost(cost.outputCost)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Cache write</div>
            <div className="font-mono text-yellow-500">
              {step.cacheWriteTokens.toLocaleString()}
            </div>
            <div className="font-mono text-xs text-muted-foreground">{formatCost(cost.cacheWriteCost)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Cache read</div>
            <div className="font-mono text-purple-500">
              {step.cacheReadTokens.toLocaleString()}
            </div>
            <div className="font-mono text-xs text-muted-foreground">{formatCost(cost.cacheReadCost)}</div>
          </div>
        </div>

        {/* Render the actual message */}
        {message ? (
          <MessageCard message={message} />
        ) : (
          <p className="text-sm text-muted-foreground">
            Message content not available.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function LargestSteps({
  steps,
  activeFilter,
  messages,
  model,
}: {
  steps: ContextStep[];
  activeFilter: Category | null;
  messages: ProcessedMessage[];
  model?: string;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = activeFilter
    ? steps.filter((s) => s.category === activeFilter)
    : steps;

  const messageMap = useMemo(() => {
    const m = new Map<string, ProcessedMessage>();
    for (const msg of messages) m.set(msg.id, msg);
    return m;
  }, [messages]);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">
          Largest Context Steps
          {activeFilter && (
            <Badge variant="secondary" className="ml-2 text-xs">
              {CATEGORY_LABELS[activeFilter]}
            </Badge>
          )}
          <span className="font-normal text-muted-foreground ml-2">
            ({filtered.length} steps)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          <div className="grid grid-cols-[1fr_60px_70px_70px_70px_70px_70px_70px] gap-2 text-xs font-medium text-muted-foreground pb-2 border-b">
            <span>Step</span>
            <span>Type</span>
            <span className="text-right">Input</span>
            <span className="text-right">Output</span>
            <span className="text-right">Cache W</span>
            <span className="text-right">Cache R</span>
            <span className="text-right">Total</span>
            <span className="text-right">Cost</span>
          </div>
          {filtered.slice(0, 50).map((step, i) => {
            const isExpanded = expandedId === step.messageId;
            const stepCost = calculateCost(
              { inputTokens: step.inputTokens, outputTokens: step.outputTokens, cacheWriteTokens: step.cacheWriteTokens, cacheReadTokens: step.cacheReadTokens },
              model
            );
            return (
              <div key={`${step.messageId}-${i}`}>
                <button
                  onClick={() =>
                    setExpandedId(isExpanded ? null : step.messageId)
                  }
                  className={cn(
                    "grid grid-cols-[1fr_60px_70px_70px_70px_70px_70px_70px] gap-2 text-xs py-1.5 border-b border-border/50 w-full text-left transition-colors",
                    isExpanded
                      ? "bg-accent/50"
                      : "hover:bg-muted/30"
                  )}
                >
                  <span className="flex items-center gap-1.5 min-w-0">
                    <ChevronDown
                      className={cn(
                        "h-3 w-3 shrink-0 transition-transform text-muted-foreground",
                        isExpanded && "rotate-180"
                      )}
                    />
                    <span className="text-muted-foreground w-5 shrink-0 text-right">
                      #{step.index + 1}
                    </span>
                    <span className="truncate" title={step.label}>
                      {step.label}
                    </span>
                  </span>
                  <span>
                    <span
                      className="inline-block w-2 h-2 rounded-sm mr-1"
                      style={{
                        backgroundColor:
                          CATEGORY_COLORS[step.category] || "#6b7280",
                      }}
                    />
                    <span className="text-muted-foreground">
                      {step.category === "conversation"
                        ? "conv"
                        : step.category}
                    </span>
                  </span>
                  <span className="text-right font-mono text-blue-500">
                    {formatTokens(step.inputTokens)}
                  </span>
                  <span className="text-right font-mono text-green-500">
                    {formatTokens(step.outputTokens)}
                  </span>
                  <span className="text-right font-mono text-yellow-500">
                    {formatTokens(step.cacheWriteTokens)}
                  </span>
                  <span className="text-right font-mono text-purple-500">
                    {formatTokens(step.cacheReadTokens)}
                  </span>
                  <span className="text-right font-mono font-medium">
                    {formatTokens(step.totalTokens)}
                  </span>
                  <span className="text-right font-mono text-amber-600 dark:text-amber-400">
                    {formatCost(stepCost.totalCost)}
                  </span>
                </button>
                {isExpanded && (
                  <div className="py-3 px-1">
                    <StepDetail
                      step={step}
                      message={messageMap.get(step.messageId)}
                      onClose={() => setExpandedId(null)}
                      model={model}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

export function ContextTab({
  analytics,
  totalUsage,
  messages,
  model,
  contextWindow,
}: {
  analytics: ContextAnalytics;
  totalUsage: TokenUsage;
  messages: ProcessedMessage[];
  model?: string;
  contextWindow?: ContextWindowStats;
}) {
  const [categoryFilter, setCategoryFilter] = useState<Category | null>(null);

  if (analytics.buckets.length === 0) {
    return (
      <p className="text-muted-foreground text-sm mt-4">
        No context data available for this conversation.
      </p>
    );
  }

  return (
    <div className="space-y-6 mt-4">
      {/* Context window explainer */}
      {contextWindow && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-6 flex-wrap">
              <div>
                <div className="text-xs text-muted-foreground">Peak Context Window</div>
                <div className="text-lg font-bold font-mono">{formatTokens(contextWindow.peakContextWindow)}</div>
                <div className="text-xs text-muted-foreground">Largest single API call</div>
              </div>
              <div className="text-2xl text-muted-foreground/30 font-light">vs</div>
              <div>
                <div className="text-xs text-muted-foreground">Cumulative Tokens</div>
                <div className="text-lg font-bold font-mono">{formatTokens(contextWindow.cumulativeTokens)}</div>
                <div className="text-xs text-muted-foreground">Sum across {contextWindow.apiCalls} API calls</div>
              </div>
              <div className="flex-1 text-xs text-muted-foreground max-w-sm">
                The cumulative total is {contextWindow.apiCalls}x the peak because each API call re-sends the conversation history.
                Prompt caching makes re-reads cheap (0.1x input price).
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Token type legend */}
      <div className="flex gap-4 text-xs">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-blue-500" /> Input
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-green-500" /> Output
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-yellow-500" /> Cache write
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-purple-500" /> Cache read
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6">
        <CategorySummary
          analytics={analytics}
          totalUsage={totalUsage}
          activeFilter={categoryFilter}
          onFilterChange={setCategoryFilter}
          model={model}
        />
        <ToolBreakdownChart
          buckets={analytics.buckets}
          activeFilter={categoryFilter}
        />
      </div>

      <LargestSteps
        steps={analytics.steps}
        activeFilter={categoryFilter}
        messages={messages}
        model={model}
      />
    </div>
  );
}
