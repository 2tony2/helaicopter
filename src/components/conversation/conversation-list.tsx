"use client";

import { useState } from "react";
import Link from "next/link";
import { useConversations, useProjects } from "@/hooks/use-conversations";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { DateRangePicker } from "@/components/ui/date-range-picker";
import { ProviderFilter, type Provider } from "@/components/ui/provider-filter";
import { formatDistanceToNow } from "date-fns";
import { MessageSquare, Wrench, Bot, ListChecks, Database, DollarSign } from "lucide-react";
import { getModelBadgeClasses, formatModelName } from "@/lib/utils";
import { calculateCost, formatCost } from "@/lib/pricing";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function ConversationList() {
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState<string>();
  const [days, setDays] = useState<number | undefined>(7);
  const [provider, setProvider] = useState<Provider>("all");
  const [threadTypeFilter, setThreadTypeFilter] = useState<"all" | "main" | "subagent">("all");
  const { data: conversations, isLoading } = useConversations(projectFilter, days);
  const { data: projects } = useProjects();

  const filtered = conversations?.filter((c) => {
    // Provider filter
    if (provider === "codex" && !c.projectPath.startsWith("codex:")) return false;
    if (provider === "claude" && c.projectPath.startsWith("codex:")) return false;
    if (threadTypeFilter !== "all" && c.threadType !== threadTypeFilter) return false;

    if (!search) return true;
    const q = search.toLowerCase();
    return (
      c.firstMessage.toLowerCase().includes(q) ||
      c.projectName.toLowerCase().includes(q) ||
      c.gitBranch?.toLowerCase().includes(q)
    );
  }).sort((a, b) => b.lastUpdatedAt - a.lastUpdatedAt);

  return (
    <div className="space-y-4">
      <div className="flex gap-3 flex-wrap items-start">
        <div className="flex gap-3 flex-wrap items-center">
          <Input
            placeholder="Search conversations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
          />
          <select
            className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={projectFilter || ""}
            onChange={(e) => setProjectFilter(e.target.value || undefined)}
          >
            <option value="">All projects</option>
            {projects?.map((p) => (
              <option key={p.encodedPath} value={p.encodedPath}>
                {p.displayName}
              </option>
            ))}
          </select>
          <DateRangePicker value={days} onChange={setDays} />
          <ProviderFilter value={provider} onChange={setProvider} />
          {conversations && (
            <span className="text-sm text-muted-foreground">
              {filtered?.length ?? conversations.length} conversations
            </span>
          )}
        </div>
        <div className="ml-auto">
          <select
            className="flex h-9 min-w-[180px] rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={threadTypeFilter}
            onChange={(e) =>
              setThreadTypeFilter(e.target.value as "all" | "main" | "subagent")
            }
            aria-label="Filter by thread type"
          >
            <option value="all">All conversations</option>
            <option value="main">Main threads</option>
            <option value="subagent">Sub-agents</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered?.map((conv) => (
            <Link
              key={`${conv.projectPath}/${conv.sessionId}`}
              href={`/conversations/${encodeURIComponent(conv.projectPath)}/${conv.sessionId}`}
            >
              <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {conv.firstMessage || "(empty conversation)"}
                      </p>
                      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                        <Badge variant="outline" className="text-xs">
                          {conv.projectName}
                        </Badge>
                        {conv.gitBranch && (
                          <Badge variant="secondary" className="text-xs">
                            {conv.gitBranch}
                          </Badge>
                        )}
                        <Badge variant="outline" className="text-xs capitalize">
                          {conv.threadType === "subagent" ? "sub-agent" : "main"}
                        </Badge>
                        {conv.model && (
                          <Badge className={`text-xs border-0 ${getModelBadgeClasses(conv.model)}`}>
                            {formatModelName(conv.model)}
                          </Badge>
                        )}
                        {conv.reasoningEffort && (
                          <Badge variant="outline" className="text-xs">
                            effort: {conv.reasoningEffort}
                          </Badge>
                        )}
                        {conv.speed === "fast" && (
                          <Badge variant="outline" className="text-xs text-amber-600 dark:text-amber-400 border-amber-300 dark:border-amber-600">
                            fast
                          </Badge>
                        )}
                        {conv.isRunning && (
                          <Badge variant="outline" className="text-xs gap-2 border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-400">
                            <span className="relative flex h-2.5 w-2.5">
                              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                            </span>
                            running
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <span className="text-xs text-muted-foreground">
                        updated{" "}
                        {conv.lastUpdatedAt
                          ? formatDistanceToNow(conv.lastUpdatedAt, { addSuffix: true })
                          : ""}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        created{" "}
                        {conv.createdAt
                          ? formatDistanceToNow(conv.createdAt, { addSuffix: true })
                          : ""}
                      </span>
                      <div className="flex items-center gap-2.5 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1" title="Messages">
                          <MessageSquare className="h-3 w-3" />
                          {conv.messageCount}
                        </span>
                        <span className="flex items-center gap-1" title="Tool calls">
                          <Wrench className="h-3 w-3" />
                          {conv.toolUseCount}
                        </span>
                        {conv.subagentCount > 0 && (
                          <span className="flex items-center gap-1" title="Sub-agents">
                            <Bot className="h-3 w-3" />
                            {conv.subagentCount}
                          </span>
                        )}
                        {conv.taskCount > 0 && (
                          <span className="flex items-center gap-1" title="Tasks">
                            <ListChecks className="h-3 w-3" />
                            {conv.taskCount}
                          </span>
                        )}
                        <span
                          className="flex items-center gap-1 font-mono"
                          title={
                            conv.projectPath.startsWith("codex:")
                              ? `Input: ${conv.totalInputTokens.toLocaleString()} / Output: ${conv.totalOutputTokens.toLocaleString()} / Cached input: ${conv.totalCacheReadTokens.toLocaleString()}`
                              : `Input: ${conv.totalInputTokens.toLocaleString()} / Output: ${conv.totalOutputTokens.toLocaleString()} / Cache write: ${conv.totalCacheCreationTokens.toLocaleString()} / Cache read: ${conv.totalCacheReadTokens.toLocaleString()}`
                          }
                        >
                          <Database className="h-3 w-3" />
                          {formatTokens(conv.totalInputTokens + conv.totalOutputTokens + conv.totalCacheCreationTokens + conv.totalCacheReadTokens)}
                        </span>
                        <span className="flex items-center gap-1 font-mono text-amber-600 dark:text-amber-400" title="Estimated cost">
                          <DollarSign className="h-3 w-3" />
                          {formatCost(calculateCost({
                            inputTokens: conv.totalInputTokens,
                            outputTokens: conv.totalOutputTokens,
                            cacheWriteTokens: conv.totalCacheCreationTokens,
                            cacheReadTokens: conv.totalCacheReadTokens,
                          }, conv.model).totalCost)}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
          {filtered?.length === 0 && (
            <p className="text-center text-muted-foreground py-8">
              No conversations found
            </p>
          )}
        </div>
      )}
    </div>
  );
}
