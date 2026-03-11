"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  useConversation,
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
import { Bot, ExternalLink, ChevronLeft, Database, Gauge, Download, Brain, FileText, AlertTriangle } from "lucide-react";
import { getModelBadgeClasses, formatModelName } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { DisplayToolCallBlock, ProcessedMessage, SubagentInfo, TokenUsage } from "@/lib/types";
import { ContextTab } from "./context-tab";
import { PlanPanel } from "@/components/plans/plan-panel";
import { ToolCallBlock } from "./tool-call-block";
import { EvaluationDialog } from "./evaluation-dialog";
import { EvaluationsTab } from "./evaluations-tab";

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

function SubagentCard({
  agent,
  onSelect,
}: {
  agent: SubagentInfo;
  onSelect: (agentId: string) => void;
}) {
  return (
    <Card
      className={`cursor-pointer transition-colors ${
        agent.hasFile
          ? "hover:bg-accent/50"
          : "opacity-60 cursor-default"
      }`}
      onClick={() => agent.hasFile && onSelect(agent.agentId)}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <Bot className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              {agent.nickname && (
                <span className="text-sm font-medium">{agent.nickname}</span>
              )}
              <span className="font-mono text-sm font-medium">
                {agent.agentId}
              </span>
              {agent.subagentType && (
                <Badge variant="secondary" className="text-xs">
                  {agent.subagentType}
                </Badge>
              )}
              {!agent.hasFile && (
                <Badge variant="outline" className="text-xs text-muted-foreground">
                  no file
                </Badge>
              )}
            </div>
            {agent.description && (
              <p className="text-sm text-muted-foreground mt-1 truncate">
                {agent.description}
              </p>
            )}
          </div>
          {agent.hasFile && (
            <ExternalLink className="h-4 w-4 text-muted-foreground shrink-0 mt-1" />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SubagentViewer({
  projectPath,
  sessionId,
  agentId,
  nickname,
  subagentType,
  onBack,
}: {
  projectPath: string;
  sessionId: string;
  agentId: string;
  nickname?: string;
  subagentType?: string;
  onBack: () => void;
}) {
  const { data: conversation, isLoading } = useSubagentConversation(
    projectPath,
    sessionId,
    agentId
  );
  const provider = providerFromProjectPath(projectPath);

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to sub-agents list
      </button>

      <div className="flex items-center gap-2">
        <Bot className="h-5 w-5" />
        {nickname && <span className="font-medium">{nickname}</span>}
        <span className="font-mono font-medium">{agentId}</span>
        {subagentType && (
          <Badge variant="secondary" className="text-xs">
            {subagentType}
          </Badge>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : conversation ? (
        <div className="space-y-4">
          <div className="flex items-center gap-3 flex-wrap">
            {conversation.model && (
              <Badge className={`text-xs border-0 ${getModelBadgeClasses(conversation.model)}`}>
                {formatModelName(conversation.model)}
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
        </div>
      ) : (
        <p className="text-muted-foreground text-sm">
          Could not load sub-agent conversation.
        </p>
      )}
    </div>
  );
}

export function ConversationViewer({
  projectPath,
  sessionId,
}: {
  projectPath: string;
  sessionId: string;
}) {
  const { data: conversation, isLoading, error } = useConversation(projectPath, sessionId);
  const { data: evaluations, mutate: mutateEvaluations } = useConversationEvaluations(
    projectPath,
    sessionId
  );
  const { data: tasks } = useTasks(sessionId);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [showEvaluationToast, setShowEvaluationToast] = useState(false);
  const plans = conversation?.plans || [];

  useEffect(() => {
    if (!showEvaluationToast) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setShowEvaluationToast(false);
    }, 3500);

    return () => window.clearTimeout(timeout);
  }, [showEvaluationToast]);

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
  const selectedSubagent = subagents.find((agent) => agent.agentId === selectedAgent);
  const selectedPlan = plans.find((plan) => plan.id === selectedPlanId) || plans[0];
  const conversationEvaluations = evaluations ?? [];
  const provider = providerFromProjectPath(projectPath);

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
            {conversation.startTime
              ? format(conversation.startTime, "MMM d, yyyy h:mm a")
              : ""}
          </span>
        </div>

        <EvaluationDialog
          projectPath={projectPath}
          sessionId={sessionId}
          onCreated={(evaluation) => {
            void mutateEvaluations((current) => [evaluation, ...(current ?? [])], false);
          }}
          onSubmitted={() => setShowEvaluationToast(true)}
        />
      </div>

      <Tabs defaultValue="messages">
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
              <MessageCard key={message.id} message={message} provider={provider} />
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
                      onClick={() => setSelectedPlanId(plan.id)}
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

        <TabsContent value="subagents">
          <div className="mt-4">
            {selectedAgent ? (
              <SubagentViewer
                projectPath={projectPath}
                sessionId={sessionId}
                agentId={selectedAgent}
                nickname={selectedSubagent?.nickname}
                subagentType={selectedSubagent?.subagentType}
                onBack={() => setSelectedAgent(null)}
              />
            ) : subagents.length > 0 ? (
              <div className="space-y-2">
                {subagents.map((agent) => (
                  <SubagentCard
                    key={agent.agentId}
                    agent={agent}
                    onSelect={setSelectedAgent}
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
