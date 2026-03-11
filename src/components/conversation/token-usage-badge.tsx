"use client";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { TokenUsage } from "@/lib/types";
import { calculateCost, formatCost } from "@/lib/pricing";
import { ArrowDownToLine, ArrowUpFromLine, DatabaseZap, BookOpen, Brain } from "lucide-react";
import { isOpenAIModel } from "@/lib/utils";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function TokenBadge({
  icon: Icon,
  tokens,
  cost,
  label,
  colorClass,
}: {
  icon: React.ComponentType<{ className?: string }>;
  tokens: number;
  cost: number;
  label: string;
  colorClass: string;
}) {
  if (!tokens) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className="text-xs font-mono gap-1 px-1.5">
          <Icon className={`h-3 w-3 ${colorClass}`} />
          <span className={colorClass}>{formatTokens(tokens)}</span>
        </Badge>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="font-mono text-xs">
        <div>
          {label}: {tokens.toLocaleString()} tokens
        </div>
        <div className="text-muted-foreground">{formatCost(cost)}</div>
      </TooltipContent>
    </Tooltip>
  );
}

export function TokenUsageBadge({
  usage,
  model,
  reasoningTokens,
  provider,
}: {
  usage?: TokenUsage;
  model?: string;
  reasoningTokens?: number;
  provider?: "claude" | "codex";
}) {
  if (!usage) return null;

  const cost = calculateCost(usage, model);
  const openAIUsage = provider === "codex" || isOpenAIModel(model);
  const cacheReadLabel = openAIUsage ? "Cached input" : "Cache read";

  return (
    <div className="flex items-center gap-1">
      <TokenBadge
        icon={ArrowDownToLine}
        tokens={usage.input_tokens}
        cost={cost.inputCost}
        label="Input"
        colorClass="text-blue-500"
      />
      <TokenBadge
        icon={ArrowUpFromLine}
        tokens={usage.output_tokens}
        cost={cost.outputCost}
        label="Output"
        colorClass="text-green-500"
      />
      {!openAIUsage && (
        <TokenBadge
          icon={DatabaseZap}
          tokens={usage.cache_creation_input_tokens || 0}
          cost={cost.cacheWriteCost}
          label="Cache write"
          colorClass="text-yellow-500"
        />
      )}
      <TokenBadge
        icon={BookOpen}
        tokens={usage.cache_read_input_tokens || 0}
        cost={cost.cacheReadCost}
        label={cacheReadLabel}
        colorClass="text-purple-500"
      />
      {reasoningTokens != null && reasoningTokens > 0 && (
        <TokenBadge
          icon={Brain}
          tokens={reasoningTokens}
          cost={0}
          label="Reasoning"
          colorClass="text-amber-500"
        />
      )}
      {/* Total cost badge */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant="secondary" className="text-xs font-mono px-1.5">
            {formatCost(cost.totalCost)}
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="font-mono text-xs">
          <div className="space-y-0.5">
            <div>Input: {formatCost(cost.inputCost)}</div>
            <div>Output: {formatCost(cost.outputCost)}</div>
            {!openAIUsage && (
              <div>Cache write: {formatCost(cost.cacheWriteCost)}</div>
            )}
            <div>{cacheReadLabel}: {formatCost(cost.cacheReadCost)}</div>
            <div className="border-t pt-0.5 font-medium">
              Total: {formatCost(cost.totalCost)}
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
