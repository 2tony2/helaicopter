"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import {
  Bot,
  Database,
  DollarSign,
  GitBranch,
  MessageSquare,
  Network,
  Wrench,
} from "lucide-react";
import {
  useConversationDagSummaries,
  useProjects,
} from "@/hooks/use-conversations";
import { DateRangePicker } from "@/components/ui/date-range-picker";
import { ProviderFilter, type Provider } from "@/components/ui/provider-filter";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { calculateCost, formatCost } from "@/lib/pricing";
import { getModelBadgeClasses, formatModelName } from "@/lib/utils";
import { buildConversationTabRoute, buildConversationRoute } from "@/lib/routes";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function ConversationDagList() {
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState<string>();
  const [days, setDays] = useState<number | undefined>(7);
  const [provider, setProvider] = useState<Provider>("all");
  const { data: summaries, isLoading } = useConversationDagSummaries(
    projectFilter,
    days,
    provider
  );
  const { data: projects } = useProjects();

  const filtered = useMemo(() => {
    return summaries?.filter((conversation) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        conversation.firstMessage.toLowerCase().includes(q) ||
        conversation.projectName.toLowerCase().includes(q) ||
        conversation.gitBranch?.toLowerCase().includes(q)
      );
    }).sort((a, b) => b.lastUpdatedAt - a.lastUpdatedAt);
  }, [search, summaries]);

  const aggregate = useMemo(() => {
    const rows = filtered ?? [];
    const totalNodes = rows.reduce((sum, row) => sum + row.dag.totalNodes, 0);
    const totalSubagents = rows.reduce(
      (sum, row) => sum + row.dag.totalSubagentNodes,
      0
    );
    const deepestDag = rows.reduce(
      (max, row) => Math.max(max, row.dag.maxDepth),
      0
    );
    const widestDag = rows.reduce(
      (max, row) => Math.max(max, row.dag.maxBreadth),
      0
    );

    return {
      totalDags: rows.length,
      totalNodes,
      totalSubagents,
      deepestDag,
      widestDag,
    };
  }, [filtered]);

  return (
    <div className="space-y-6">
      <div className="flex gap-3 flex-wrap items-start">
        <div className="flex gap-3 flex-wrap items-center">
          <Input
            placeholder="Search DAG conversations..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="max-w-sm"
          />
          <select
            className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={projectFilter || ""}
            onChange={(event) => setProjectFilter(event.target.value || undefined)}
          >
            <option value="">All projects</option>
            {projects?.map((project) => (
              <option key={project.encodedPath} value={project.encodedPath}>
                {project.displayName}
              </option>
            ))}
          </select>
          <DateRangePicker value={days} onChange={setDays} />
          <ProviderFilter value={provider} onChange={setProvider} />
        </div>
        <div className="ml-auto text-sm text-muted-foreground">
          {filtered?.length ?? 0} DAG conversations
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              DAG conversations
            </div>
            <div className="mt-2 text-2xl font-semibold">{aggregate.totalDags}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Total nodes
            </div>
            <div className="mt-2 text-2xl font-semibold">{aggregate.totalNodes}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Deepest DAG
            </div>
            <div className="mt-2 text-2xl font-semibold">{aggregate.deepestDag}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Widest DAG
            </div>
            <div className="mt-2 text-2xl font-semibold">{aggregate.widestDag}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {aggregate.totalSubagents} total sub-agents
            </div>
          </CardContent>
        </Card>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered?.map((conversation) => (
            <Link
              key={`${conversation.projectPath}/${conversation.sessionId}`}
              href={
                conversation.conversationRef
                  ? buildConversationTabRoute(conversation.conversationRef, "messages")
                  : buildConversationRoute(conversation.projectPath, conversation.sessionId)
              }
            >
              <Card className="cursor-pointer border-slate-200 transition-colors hover:bg-accent/40">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        {conversation.firstMessage || "(empty conversation)"}
                      </div>
                      <div className="mt-2 flex items-center gap-2 flex-wrap">
                        <Badge variant="outline">{conversation.projectName}</Badge>
                        {conversation.gitBranch && (
                          <Badge variant="secondary">{conversation.gitBranch}</Badge>
                        )}
                        <Badge variant="outline">main</Badge>
                        {conversation.model && (
                          <Badge
                            className={`border-0 text-xs ${getModelBadgeClasses(conversation.model)}`}
                          >
                            {formatModelName(conversation.model)}
                          </Badge>
                        )}
                        {conversation.isRunning && (
                          <Badge variant="outline" className="text-xs gap-2 border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-400">
                            <span className="relative flex h-2.5 w-2.5">
                              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                            </span>
                            running
                          </Badge>
                        )}
                      </div>
                      <div className="mt-3 grid gap-2 md:grid-cols-3 xl:grid-cols-5">
                        <div className="rounded-xl border bg-muted/20 px-3 py-2 text-xs">
                          <div className="text-muted-foreground">Nodes</div>
                          <div className="mt-1 flex items-center gap-1 font-medium">
                            <Bot className="h-3.5 w-3.5" />
                            {conversation.dag.totalNodes}
                          </div>
                        </div>
                        <div className="rounded-xl border bg-muted/20 px-3 py-2 text-xs">
                          <div className="text-muted-foreground">Depth</div>
                          <div className="mt-1 flex items-center gap-1 font-medium">
                            <Network className="h-3.5 w-3.5" />
                            {conversation.dag.maxDepth}
                          </div>
                        </div>
                        <div className="rounded-xl border bg-muted/20 px-3 py-2 text-xs">
                          <div className="text-muted-foreground">Breadth</div>
                          <div className="mt-1 flex items-center gap-1 font-medium">
                            <GitBranch className="h-3.5 w-3.5" />
                            {conversation.dag.maxBreadth}
                          </div>
                        </div>
                        <div className="rounded-xl border bg-muted/20 px-3 py-2 text-xs">
                          <div className="text-muted-foreground">Leaves</div>
                          <div className="mt-1 flex items-center gap-1 font-medium">
                            <Wrench className="h-3.5 w-3.5" />
                            {conversation.dag.leafCount}
                          </div>
                        </div>
                        <div className="rounded-xl border bg-muted/20 px-3 py-2 text-xs">
                          <div className="text-muted-foreground">Tokens</div>
                          <div className="mt-1 flex items-center gap-1 font-medium">
                            <Database className="h-3.5 w-3.5" />
                            {formatTokens(conversation.dag.totalTokens)}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="shrink-0 text-right text-xs text-muted-foreground">
                      <div>
                        updated{" "}
                        {conversation.lastUpdatedAt
                          ? formatDistanceToNow(conversation.lastUpdatedAt, {
                              addSuffix: true,
                            })
                          : ""}
                      </div>
                      <div>
                        created{" "}
                        {conversation.createdAt
                          ? formatDistanceToNow(conversation.createdAt, {
                              addSuffix: true,
                            })
                          : ""}
                      </div>
                      <div className="mt-2 flex items-center justify-end gap-3">
                        <span className="flex items-center gap-1">
                          <MessageSquare className="h-3 w-3" />
                          {conversation.messageCount}
                        </span>
                        <span className="flex items-center gap-1">
                          <Bot className="h-3 w-3" />
                          {conversation.dag.totalSubagentNodes}
                        </span>
                        <span className="flex items-center gap-1 font-mono">
                          <DollarSign className="h-3 w-3" />
                          {formatCost(
                            calculateCost(
                              {
                                inputTokens: conversation.totalInputTokens,
                                outputTokens: conversation.totalOutputTokens,
                                cacheWriteTokens: conversation.totalCacheCreationTokens,
                                cacheReadTokens: conversation.totalCacheReadTokens,
                              },
                              conversation.model
                            ).totalCost
                          )}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
          {filtered?.length === 0 && (
            <p className="py-12 text-center text-muted-foreground">
              No main conversations with sub-agent DAGs found.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
