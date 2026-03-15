"use client";

import Link from "next/link";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import {
  AlertTriangle,
  Bot,
  Bug,
  Code2,
  FlaskConical,
  Layers3,
  MessageSquare,
  Server,
  Wrench,
} from "lucide-react";
import { useConversations, useProjects } from "@/hooks/use-conversations";
import { DEBUG_SCENARIOS, buildDebugConversationMatches, countMatchesByScenario, filterDebugConversationMatches, type DebugScenarioId } from "@/lib/debugging";
import { formatModelName, getModelBadgeClasses } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DateRangePicker } from "@/components/ui/date-range-picker";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ProviderFilter, type Provider } from "@/components/ui/provider-filter";

const scenarioIcons: Record<DebugScenarioId, typeof Bug> = {
  editing: Bug,
  frontend: Code2,
  backend: Server,
  tests: FlaskConical,
  "tool-failures": AlertTriangle,
  "multi-agent": Bot,
};

function providerLabel(projectPath: string): "Claude" | "Codex" {
  return projectPath.startsWith("codex:") ? "Codex" : "Claude";
}

function formatTools(toolBreakdown: Record<string, number>): string[] {
  return Object.entries(toolBreakdown)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([name, count]) => `${name} x${count}`);
}

export function DebuggingDashboard() {
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState<string>();
  const [days, setDays] = useState<number | undefined>(30);
  const [provider, setProvider] = useState<Provider>("all");
  const [threadType, setThreadType] = useState<"all" | "main" | "subagent">("all");
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<DebugScenarioId[]>(["editing"]);
  const { data: conversations, isLoading } = useConversations(projectFilter, days);
  const { data: projects } = useProjects();

  const debugMatches = buildDebugConversationMatches(conversations ?? []);
  const scenarioCounts = countMatchesByScenario(
    filterDebugConversationMatches(debugMatches, {
      provider,
      threadType,
    })
  );
  const filteredMatches = filterDebugConversationMatches(debugMatches, {
    provider,
    threadType,
    search,
    selectedScenarioIds,
  });

  function toggleScenario(id: DebugScenarioId) {
    setSelectedScenarioIds((current) =>
      current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id]
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Debugging</h1>
          <p className="text-muted-foreground mt-1">
            Find editing-related conversations by intent, tools, failures, and subagent activity.
          </p>
        </div>
        <Badge variant="outline" className="gap-1.5 text-xs">
          <Layers3 className="h-3 w-3" />
          {filteredMatches.length} matching conversations
        </Badge>
      </div>

      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="flex gap-3 flex-wrap items-start">
            <Input
              placeholder="Search prompts, branches, projects, or tools..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="max-w-md"
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
            <select
              className="flex h-9 min-w-[170px] rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={threadType}
              onChange={(event) =>
                setThreadType(event.target.value as "all" | "main" | "subagent")
              }
              aria-label="Filter by thread type"
            >
              <option value="all">All thread types</option>
              <option value="main">Main threads</option>
              <option value="subagent">Sub-agents</option>
            </select>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setSearch("");
                setProjectFilter(undefined);
                setDays(30);
                setProvider("all");
                setThreadType("all");
                setSelectedScenarioIds(["editing"]);
              }}
            >
              Reset
            </Button>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {DEBUG_SCENARIOS.map((scenario) => {
              const Icon = scenarioIcons[scenario.id];
              const isActive = selectedScenarioIds.includes(scenario.id);
              return (
                <button
                  key={scenario.id}
                  type="button"
                  onClick={() => toggleScenario(scenario.id)}
                  className={`rounded-xl border p-4 text-left transition-colors ${
                    isActive ? "border-primary bg-primary/5" : "hover:bg-accent/50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 font-medium">
                      <Icon className="h-4 w-4" />
                      {scenario.label}
                    </div>
                    <Badge variant={isActive ? "default" : "outline"} className="font-mono">
                      {scenarioCounts[scenario.id]}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {scenario.description}
                  </p>
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-2 flex-wrap text-sm text-muted-foreground">
            <span>Active filters:</span>
            {selectedScenarioIds.length > 0 ? (
              selectedScenarioIds.map((scenarioId) => (
                <Badge key={scenarioId} variant="secondary">
                  {DEBUG_SCENARIOS.find((scenario) => scenario.id === scenarioId)?.label}
                </Badge>
              ))
            ) : (
              <Badge variant="outline">All debug signals</Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-32 w-full" />
          ))}
        </div>
      ) : filteredMatches.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            No conversations matched the current debugging filters.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredMatches.map((row) => {
            const tools = formatTools(row.conversation.toolBreakdown);
            return (
              <Card key={`${row.conversation.projectPath}/${row.conversation.sessionId}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-2 min-w-0">
                      <CardTitle className="text-base leading-snug">
                        {row.conversation.firstMessage || "(empty conversation)"}
                      </CardTitle>
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline">{row.conversation.projectName}</Badge>
                        <Badge variant="secondary">{providerLabel(row.conversation.projectPath)}</Badge>
                        <Badge variant="outline" className="capitalize">
                          {row.conversation.threadType === "subagent" ? "sub-agent" : "main"}
                        </Badge>
                        {row.conversation.gitBranch ? (
                          <Badge variant="outline">{row.conversation.gitBranch}</Badge>
                        ) : null}
                        {row.conversation.model ? (
                          <Badge className={`border-0 text-xs ${getModelBadgeClasses(row.conversation.model)}`}>
                            {formatModelName(row.conversation.model)}
                          </Badge>
                        ) : null}
                      </div>
                    </div>
                    <div className="text-right shrink-0 space-y-1">
                      <div className="text-xs text-muted-foreground">
                        {formatDistanceToNow(row.conversation.timestamp, { addSuffix: true })}
                      </div>
                      <Badge variant="outline" className="font-mono">
                        score {row.score}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-4 flex-wrap text-sm text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <MessageSquare className="h-4 w-4" />
                      {row.conversation.messageCount} messages
                    </span>
                    <span className="flex items-center gap-1">
                      <Wrench className="h-4 w-4" />
                      {row.conversation.toolUseCount} tool calls
                    </span>
                    {row.conversation.failedToolCallCount > 0 ? (
                      <span className="flex items-center gap-1 text-destructive">
                        <AlertTriangle className="h-4 w-4" />
                        {row.conversation.failedToolCallCount} failed
                      </span>
                    ) : null}
                    {row.conversation.subagentCount > 0 ? (
                      <span className="flex items-center gap-1">
                        <Bot className="h-4 w-4" />
                        {row.conversation.subagentCount} subagents
                      </span>
                    ) : null}
                  </div>

                  <div className="space-y-2">
                    <div className="text-sm font-medium">Matched signals</div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {row.matches.map((match) => (
                        <Badge key={match.id} variant="secondary">
                          {match.label}
                        </Badge>
                      ))}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {row.reasons.map((reason) => (
                        <Badge key={reason} variant="outline" className="max-w-full whitespace-normal">
                          {reason}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {tools.length > 0 ? (
                    <div className="space-y-2">
                      <div className="text-sm font-medium">Top tools</div>
                      <div className="flex items-center gap-2 flex-wrap">
                        {tools.map((tool) => (
                          <Badge key={tool} variant="outline">
                            {tool}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <div>
                    <Button asChild>
                      <Link
                        href={`/conversations/${encodeURIComponent(row.conversation.projectPath)}/${row.conversation.sessionId}`}
                      >
                        Open conversation
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
