"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  useConversation,
  useConversationDag,
  useConversationEvaluations,
  useTasks,
  useSubagentConversation,
} from "@/hooks/use-conversations";
import { MessageCard } from "./message-card";
import { TokenUsageBadge } from "./token-usage-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { format } from "date-fns";
import { Bot, Database, Gauge, Download, Brain, FileText, AlertTriangle } from "lucide-react";
import { getModelBadgeClasses, formatModelName } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { DisplayToolCallBlock, ProcessedMessage, SubagentInfo, TokenUsage } from "@/lib/types";
import { ContextTab } from "./context-tab";
import { PlanPanel } from "@/components/plans/plan-panel";
import { ToolCallBlock } from "./tool-call-block";
import { EvaluationDialog } from "./evaluation-dialog";
import { EvaluationsTab } from "./evaluations-tab";
import { ConversationDagView } from "./conversation-dag-view";
import {
  buildConversationRoute,
  buildConversationSubagentRoute,
  getConversationRouteState,
  type ConversationDetailTab,
} from "@/lib/routes";

function providerLabel(provider: "claude" | "codex"): string {
  return provider === "claude" ? "Claude" : "Codex";
}

function providerDotClass(provider: "claude" | "codex"): string {
  return provider === "claude" ? "bg-emerald-500" : "bg-sky-500";
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function totalContext(usage: TokenUsage): number {
  return (
    (usage.input_tokens || 0) +
    (usage.output_tokens || 0) +
    (usage.cache_creation_input_tokens || 0) +
    (usage.cache_read_input_tokens || 0)
  );
}

function providerFromProjectPath(projectPath: string): "claude" | "codex" {
  return projectPath.startsWith("codex:") ? "codex" : "claude";
}

interface FailedToolCallEntry {
  message: ProcessedMessage;
  block: DisplayToolCallBlock;
  index: number;
}

function FailedToolCallsTab({
  failures,
}: {
  failures: FailedToolCallEntry[];
}) {
  if (failures.length === 0) {
    return (
      <p className="text-muted-foreground text-sm mt-4">
        No failed tool calls were captured for this conversation.
      </p>
    );
  }

  return (
    <div className="space-y-4 mt-4">
      {failures.map((failure) => (
        <Card key={`${failure.message.id}:${failure.index}`} className="border-destructive/30">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant={failure.message.role === "user" ? "default" : "secondary"}>
                {failure.message.role}
              </Badge>
              <Badge variant="outline" className="text-xs gap-1 text-destructive border-destructive/40">
                <AlertTriangle className="h-3 w-3" />
                failed tool call
              </Badge>
              <span className="text-xs text-muted-foreground">
                {format(failure.message.timestamp, "MMM d, yyyy h:mm:ss a")}
              </span>
            </div>
            <ToolCallBlock block={failure.block} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function SubagentTranscriptCard({
  projectPath,
  sessionId,
  parentSessionId,
  agent,
  isSelected = false,
  depth = 0,
  ancestry = [],
}: {
  projectPath: string;
  sessionId: string;
  parentSessionId?: string;
  agent: SubagentInfo;
  isSelected?: boolean;
  depth?: number;
  ancestry?: string[];
}) {
  const {
    data: conversation,
    isLoading,
    error,
  } = useSubagentConversation(
    projectPath,
    parentSessionId ?? sessionId,
    agent.agentId
  );
  const provider = providerFromProjectPath(projectPath);
  const nestedSubagents = (conversation?.subagents ?? []).filter(
    (child) => child.agentId !== agent.agentId && !ancestry.includes(child.agentId)
  );

  return (
    <div
      className={depth > 0 ? "border-l border-border/60 pl-4" : undefined}
      style={depth > 0 ? { marginLeft: `${depth * 12}px` } : undefined}
    >
      <Card
        id={depth === 0 ? `subagent-${agent.agentId}` : undefined}
        className={[
          !agent.hasFile ? "opacity-70" : "",
          isSelected ? "border-primary ring-1 ring-primary/30" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <CardContent className="p-4 space-y-4">
          <div className="flex items-start gap-3">
            <Bot className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0 space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                {agent.nickname && <span className="text-sm font-medium">{agent.nickname}</span>}
                <span className="font-mono text-sm font-medium">{agent.agentId}</span>
                {agent.subagentType && (
                  <Badge variant="secondary" className="text-xs">
                    {agent.subagentType}
                  </Badge>
                )}
                <Badge variant="outline" className="text-xs">
                  sub-agent
                </Badge>
                <Link
                  href={buildConversationSubagentRoute(
                    projectPath,
                    parentSessionId ?? sessionId,
                    agent.agentId
                  )}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  native route
                </Link>
                {!agent.hasFile && (
                  <Badge variant="outline" className="text-xs text-muted-foreground">
                    no file
                  </Badge>
                )}
              </div>
              {agent.description && (
                <p className="text-sm text-muted-foreground">{agent.description}</p>
              )}
            </div>
          </div>

          {!agent.hasFile ? (
            <p className="text-sm text-muted-foreground">
              Full sub-agent transcript is not available for this entry.
            </p>
          ) : isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : error || !conversation ? (
            <p className="text-sm text-muted-foreground">
              Could not load sub-agent conversation.
            </p>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3 flex-wrap">
                {conversation.model && (
                  <Badge className={`text-xs border-0 ${getModelBadgeClasses(conversation.model)}`}>
                    {formatModelName(conversation.model)}
                  </Badge>
                )}
                {conversation.totalReasoningTokens && conversation.totalReasoningTokens > 0 && (
                  <Badge
                    variant="outline"
                    className="text-xs font-mono gap-1 text-amber-600 dark:text-amber-400"
                  >
                    <Brain className="h-3 w-3" />
                    {formatTokens(conversation.totalReasoningTokens)} reasoning
                  </Badge>
                )}
                <TokenUsageBadge
                  usage={conversation.totalUsage}
                  model={conversation.model}
                  provider={provider}
                />
                <Badge variant="outline" className="text-xs font-mono gap-1">
                  <Database className="h-3 w-3" />
                  {formatTokens(totalContext(conversation.totalUsage))} context
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {conversation.messages.length} messages
                </span>
              </div>

              <div className="space-y-4">
                {conversation.messages.map((message) => (
                  <MessageCard key={message.id} message={message} provider={provider} />
                ))}
              </div>

              {nestedSubagents.length > 0 && (
                <div className="space-y-4">
                  <div className="text-sm font-medium">Nested sub-agents</div>
                  {nestedSubagents.map((child) => (
                    <SubagentTranscriptCard
                      key={`${agent.agentId}:${child.agentId}`}
                      projectPath={projectPath}
                      sessionId={sessionId}
                      parentSessionId={agent.agentId}
                      agent={child}
                      depth={depth + 1}
                      ancestry={[...ancestry, agent.agentId]}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function ConversationViewer({
  conversationRef: _conversationRef,
  projectPath,
  sessionId,
  parentSessionId,
  initialTab = "messages",
  initialPlanId,
  initialSubagentId,
  initialMessageId,
}: {
  conversationRef?: string;
  projectPath: string;
  sessionId: string;
  parentSessionId?: string;
  initialTab?: ConversationDetailTab;
  initialPlanId?: string;
  initialSubagentId?: string;
  initialMessageId?: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: conversation, isLoading, error } = useConversation(
    projectPath,
    sessionId,
    parentSessionId
  );
  const {
    data: conversationDag,
    isLoading: isDagLoading,
    error: dagError,
  } = useConversationDag(projectPath, sessionId, parentSessionId);
  const { data: evaluations, mutate: mutateEvaluations } = useConversationEvaluations(
    projectPath,
    sessionId,
    parentSessionId
  );
  const { data: tasks } = useTasks(sessionId, parentSessionId);
  const [showEvaluationToast, setShowEvaluationToast] = useState(false);
  const plans = conversation?.plans || [];
  const routeState = getConversationRouteState(searchParams, {
    tab: initialTab,
    plan: initialPlanId,
    subagent: initialSubagentId,
    message: initialMessageId,
  });
  void _conversationRef;

  useEffect(() => {
    if (!showEvaluationToast) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setShowEvaluationToast(false);
    }, 3500);

    return () => window.clearTimeout(timeout);
  }, [showEvaluationToast]);

  useEffect(() => {
    if (!routeState.subagent) {
      return;
    }
    const element = document.getElementById(`subagent-${routeState.subagent}`);
    if (element) {
      element.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }, [routeState.subagent]);

  useEffect(() => {
    if (!routeState.message) {
      return;
    }
    const element = document.getElementById(`message-${routeState.message}`);
    if (element) {
      element.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }, [routeState.message]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    );
  }

  if (error || !conversation) {
    return (
      <div className="text-center text-muted-foreground py-12">
        Failed to load conversation
      </div>
    );
  }

  const subagents = conversation.subagents || [];
  const failedToolCalls = conversation.messages.flatMap((message) =>
    message.blocks.flatMap((block, index) =>
      block.type === "tool_call" && block.isError
        ? [{ message, block, index }]
        : []
    )
  );
  const selectedPlanId = routeState.plan ?? null;
  const selectedSubagentId = routeState.subagent ?? null;
  const selectedMessageId = routeState.message ?? null;
  const activeTab = routeState.tab;
  const selectedPlan = plans.find((plan) => plan.id === selectedPlanId) || plans[0];
  const conversationEvaluations = evaluations ?? [];
  const provider = providerFromProjectPath(projectPath);

  function replaceRoute(next: {
    tab?: ConversationDetailTab;
    plan?: string | null;
    subagent?: string | null;
    message?: string | null;
  }) {
    router.replace(
      buildConversationRoute(projectPath, sessionId, {
        tab: next.tab ?? routeState.tab,
        plan: next.plan ?? routeState.plan,
        subagent: next.subagent ?? routeState.subagent,
        message: next.message ?? routeState.message,
      }),
      { scroll: false }
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          {conversation.model && (
            <Badge className={`text-xs border-0 ${getModelBadgeClasses(conversation.model)}`}>
              {formatModelName(conversation.model)}
            </Badge>
          )}
          {conversation.gitBranch && (
            <Badge variant="secondary">{conversation.gitBranch}</Badge>
          )}
          {conversation.reasoningEffort && (
            <Badge variant="outline" className="text-xs">
              effort: {conversation.reasoningEffort}
            </Badge>
          )}
          {conversation.speed === "fast" && (
            <Badge variant="outline" className="text-xs text-amber-600 dark:text-amber-400 border-amber-300 dark:border-amber-600">
              fast
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
          {conversation.totalReasoningTokens && conversation.totalReasoningTokens > 0 && (
            <Badge variant="outline" className="text-xs font-mono gap-1 text-amber-600 dark:text-amber-400">
              <Brain className="h-3 w-3" />
              {formatTokens(conversation.totalReasoningTokens)} reasoning
            </Badge>
          )}
          <TokenUsageBadge
            usage={conversation.totalUsage}
            model={conversation.model}
            provider={provider}
          />
          <Badge variant="outline" className="text-xs font-mono gap-1" title="Peak context window: largest single API call input (input + cache write + cache read)">
            <Gauge className="h-3 w-3" />
            {formatTokens(conversation.contextWindow.peakContextWindow)} peak
          </Badge>
          <Badge variant="outline" className="text-xs font-mono gap-1" title={`Cumulative tokens across ${conversation.contextWindow.apiCalls} API calls`}>
            <Database className="h-3 w-3" />
            {formatTokens(conversation.contextWindow.cumulativeTokens)} cumulative
          </Badge>
          <span className="text-sm text-muted-foreground">
            {conversation.messages.length} messages / {conversation.contextWindow.apiCalls} API calls
          </span>
          {subagents.length > 0 && (
            <span className="text-sm text-muted-foreground flex items-center gap-1">
              <Bot className="h-3.5 w-3.5" />
              {subagents.length} sub-agents
            </span>
          )}
          {plans.length > 0 && (
            <span className="text-sm text-muted-foreground flex items-center gap-1">
              <FileText className="h-3.5 w-3.5" />
              {plans.length} plans
            </span>
          )}
          {tasks && tasks.length > 0 && (
            <span className="text-sm text-muted-foreground">
              {tasks.length} tasks
            </span>
          )}
          {failedToolCalls.length > 0 && (
            <span className="text-sm text-muted-foreground flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5 text-destructive" />
              {failedToolCalls.length} failed calls
            </span>
          )}
          {conversationEvaluations.length > 0 && (
            <span className="text-sm text-muted-foreground">
              {conversationEvaluations.length} evaluations
            </span>
          )}
          <span className="text-sm text-muted-foreground">
            created{" "}
            {conversation.createdAt
              ? format(conversation.createdAt, "MMM d, yyyy h:mm a")
              : ""}
          </span>
          <span className="text-sm text-muted-foreground">
            updated{" "}
            {conversation.lastUpdatedAt
              ? format(conversation.lastUpdatedAt, "MMM d, yyyy h:mm a")
              : ""}
          </span>
        </div>

        <EvaluationDialog
          projectPath={projectPath}
          sessionId={sessionId}
          parentSessionId={parentSessionId}
          onCreated={(evaluation) => {
            void mutateEvaluations((current) => [evaluation, ...(current ?? [])], false);
          }}
          onSubmitted={() => setShowEvaluationToast(true)}
        />
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value) => {
          const nextTab = value as ConversationDetailTab;
          replaceRoute({ tab: nextTab });
        }}
      >
        <TabsList>
          <TabsTrigger value="messages">Messages</TabsTrigger>
          <TabsTrigger value="plans">
            Plans {plans.length > 0 ? `(${plans.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="evaluations">
            Evaluations {conversationEvaluations.length > 0 ? `(${conversationEvaluations.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="failed">
            Failed Calls {failedToolCalls.length > 0 ? `(${failedToolCalls.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="context">Context</TabsTrigger>
          <TabsTrigger value="dag">
            DAG {conversationDag ? `(${conversationDag.stats.totalNodes})` : ""}
          </TabsTrigger>
          <TabsTrigger value="subagents">
            Sub-agents{" "}
            {subagents.length > 0 ? `(${subagents.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="tasks">
            Tasks {tasks && tasks.length > 0 ? `(${tasks.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="raw">Raw</TabsTrigger>
        </TabsList>

        <TabsContent value="messages">
          <div className="space-y-4 mt-4">
            {conversation.messages.map((message) => (
              <MessageCard
                key={message.id}
                message={message}
                provider={provider}
                href={buildConversationRoute(projectPath, sessionId, {
                  tab: activeTab,
                  plan: selectedPlanId ?? undefined,
                  subagent: selectedSubagentId ?? undefined,
                  message: message.id,
                })}
                isSelected={selectedMessageId === message.id}
                onSelect={() => replaceRoute({ message: message.id })}
              />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="plans">
          <div className="mt-4 space-y-4">
            {plans.length > 0 && selectedPlan ? (
              <>
                <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {plans.map((plan) => (
                    <Card
                      key={plan.id}
                      className={`cursor-pointer transition-colors ${
                        selectedPlan.id === plan.id ? "border-primary" : "hover:bg-accent/50"
                      }`}
                      onClick={() => {
                        replaceRoute({ tab: "plans", plan: plan.id });
                      }}
                    >
                      <CardContent className="p-4 space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="font-medium text-sm">{plan.title}</div>
                          <Badge variant="secondary" className="text-[10px] gap-1.5">
                            <span
                              className={`h-2 w-2 rounded-full ${providerDotClass(plan.provider)}`}
                            />
                            {providerLabel(plan.provider)}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-3">
                          {plan.preview}
                        </p>
                        <div className="flex items-center gap-2 flex-wrap">
                          {plan.model ? (
                            <Badge
                              variant="outline"
                              className={`text-[10px] ${getModelBadgeClasses(plan.model)}`}
                            >
                              {formatModelName(plan.model)}
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-[10px]">
                              unknown model
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                          <span>{format(plan.timestamp, "MMM d, yyyy h:mm a")}</span>
                          <Link
                            href={`/plans/${plan.id}`}
                            className="hover:text-foreground transition-colors"
                            onClick={(event) => event.stopPropagation()}
                          >
                            Open
                          </Link>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                <Card>
                  <CardContent className="p-4">
                    <PlanPanel
                      plan={selectedPlan}
                      viewerClassName="h-[520px]"
                      extraActions={
                        <Link
                          href={`/plans/${selectedPlan.id}`}
                          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                          Open dedicated page
                        </Link>
                      }
                    />
                  </CardContent>
                </Card>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">
                No plans were captured for this conversation.
              </p>
            )}
          </div>
        </TabsContent>

        <TabsContent value="evaluations">
          <EvaluationsTab evaluations={conversationEvaluations} />
        </TabsContent>

        <TabsContent value="failed">
          <FailedToolCallsTab failures={failedToolCalls} />
        </TabsContent>

        <TabsContent value="context">
          <ContextTab
            analytics={conversation.contextAnalytics}
            totalUsage={conversation.totalUsage}
            messages={conversation.messages}
            model={conversation.model}
            contextWindow={conversation.contextWindow}
          />
        </TabsContent>

        <TabsContent value="dag">
          <div className="mt-4">
            {isDagLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-28 w-full" />
                ))}
              </div>
            ) : dagError || !conversationDag ? (
              <p className="text-sm text-muted-foreground">
                Could not build a DAG for this conversation.
              </p>
            ) : (
              <ConversationDagView dag={conversationDag} />
            )}
          </div>
        </TabsContent>

        <TabsContent value="subagents">
          <div className="mt-4">
            {subagents.length > 0 ? (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {subagents.map((agent) => (
                    <Button
                      key={`chip:${agent.agentId}`}
                      variant={selectedSubagentId === agent.agentId ? "default" : "outline"}
                      size="sm"
                      onClick={() => replaceRoute({ tab: "subagents", subagent: agent.agentId })}
                    >
                      {agent.nickname || agent.agentId}
                    </Button>
                  ))}
                </div>
                {subagents.map((agent) => (
                  <SubagentTranscriptCard
                    key={agent.agentId}
                    projectPath={projectPath}
                    sessionId={sessionId}
                    parentSessionId={sessionId}
                    agent={agent}
                    isSelected={selectedSubagentId === agent.agentId}
                  />
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">
                No sub-agents for this conversation.
              </p>
            )}
          </div>
        </TabsContent>

        <TabsContent value="tasks">
          <div className="mt-4">
            {tasks && tasks.length > 0 ? (
              <ScrollArea className="max-h-[600px]">
                <pre className="text-sm bg-muted rounded-lg p-4 font-mono whitespace-pre-wrap">
                  {JSON.stringify(tasks, null, 2)}
                </pre>
              </ScrollArea>
            ) : (
              <p className="text-muted-foreground text-sm">No tasks for this session.</p>
            )}
          </div>
        </TabsContent>

        <TabsContent value="raw">
          <div className="mt-4">
            <div className="flex justify-end mb-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const blob = new Blob([JSON.stringify(conversation, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${sessionId}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                <Download className="h-4 w-4 mr-1.5" />
                Download JSON
              </Button>
            </div>
            <ScrollArea className="h-[calc(100vh-16rem)]">
              <pre className="text-xs bg-muted rounded-lg p-4 font-mono whitespace-pre-wrap overflow-auto">
                {JSON.stringify(conversation, null, 2)}
              </pre>
            </ScrollArea>
          </div>
        </TabsContent>
      </Tabs>

      {showEvaluationToast ? (
        <Card className="fixed bottom-4 right-4 z-50 w-[320px] border-primary/20 shadow-lg">
          <CardContent className="p-4 text-sm font-medium">
            evaluation job sent to background
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
