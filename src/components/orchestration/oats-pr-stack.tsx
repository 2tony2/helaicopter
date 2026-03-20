"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { OvernightOatsRunRecord } from "@/lib/types";
import type { OatsViewModel } from "./oats-view-model";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  ExternalLink,
  GitBranch,
  GitPullRequest,
  ShieldCheck,
} from "lucide-react";

function humanizeToken(value?: string | null) {
  if (!value) {
    return "unknown";
  }
  return value.replace(/_/g, " ");
}

function checksSummaryEntries(summary?: Record<string, unknown>) {
  return Object.entries(summary ?? {}).filter(([, value]) => value !== undefined && value !== null);
}

export function OatsPrStack({
  run,
  viewModel,
  onSelectTask,
}: {
  run: OvernightOatsRunRecord;
  viewModel: OatsViewModel;
  onSelectTask: (taskId: string) => void;
}) {
  const selectedTask = viewModel.selectedTask;
  const selectedTaskChecks = checksSummaryEntries(selectedTask?.taskPr?.checksSummary);
  const finalPrChecks = checksSummaryEntries(run.finalPr?.checksSummary);

  return (
    <div className="space-y-4">
      {run.finalPr ? (
        <Card className="border-amber-500/30 bg-gradient-to-r from-amber-500/10 via-background to-background">
          <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-start md:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <ShieldCheck className="h-4 w-4 text-amber-600" />
                Final feature PR
              </div>
              <div className="text-lg font-semibold">
                {run.finalPr.headBranch ?? run.featureBranch?.name ?? run.integrationBranch}
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span>{run.finalPr.headBranch ?? run.featureBranch?.name ?? run.integrationBranch}</span>
                <ArrowRight className="h-3.5 w-3.5" />
                <span>{run.finalPr.baseBranch ?? run.finalPrTarget}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">{humanizeToken(run.finalPr.reviewGateStatus)}</Badge>
                <Badge variant="outline">state {humanizeToken(run.finalPr.state)}</Badge>
                {run.finalPr.isStale ? <Badge variant="outline">stale snapshot</Badge> : null}
                {typeof run.finalPr.number === "number" ? (
                  <Badge variant="outline">#{run.finalPr.number}</Badge>
                ) : null}
              </div>
            </div>
            <div className="space-y-2 md:text-right">
              {run.finalPr.url ? (
                <a
                  href={run.finalPr.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open final PR
                </a>
              ) : null}
              {finalPrChecks.length > 0 ? (
                <div className="flex flex-wrap gap-2 md:justify-end">
                  {finalPrChecks.map(([key, value]) => (
                    <Badge key={key} variant="outline">
                      {humanizeToken(key)} {String(value)}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card>
          <CardContent className="space-y-4 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium">Stacked task PRs</div>
                <div className="text-xs text-muted-foreground">
                  Task ancestry comes from persisted parent branches, not client inference.
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{viewModel.taskPrSummary.total} task PRs</Badge>
                <Badge variant="outline" className="border-emerald-500/30 text-emerald-700 dark:text-emerald-400">
                  {viewModel.taskPrSummary.merged} merged
                </Badge>
                {viewModel.taskPrSummary.awaitingChecks > 0 ? (
                  <Badge variant="outline">
                    {viewModel.taskPrSummary.awaitingChecks} awaiting checks
                  </Badge>
                ) : null}
                {viewModel.taskPrSummary.mergeReady > 0 ? (
                  <Badge variant="outline">{viewModel.taskPrSummary.mergeReady} merge ready</Badge>
                ) : null}
              </div>
            </div>

            <ScrollArea className="h-[420px] pr-4">
              <div className="space-y-3">
                {viewModel.stackItems.map((item) => (
                  <button
                    key={item.taskId}
                    type="button"
                    onClick={() => onSelectTask(item.taskId)}
                    className={cn(
                      "block w-full rounded-2xl border px-4 py-3 text-left transition-colors",
                      item.isSelected
                        ? "border-primary bg-primary/5 shadow-sm"
                        : "border-border/70 hover:bg-muted/40"
                    )}
                    style={{ marginLeft: `${item.depth * 18}px` }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <GitPullRequest className="h-4 w-4 text-sky-600" />
                          <span className="font-medium">{item.title}</span>
                        </div>
                        <div className="text-xs text-muted-foreground">{item.taskId}</div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span>{item.headBranch ?? "branch pending"}</span>
                          <ArrowRight className="h-3.5 w-3.5" />
                          <span>{item.baseBranch ?? item.parentBranch ?? run.featureBranch?.name ?? run.integrationBranch}</span>
                        </div>
                        {item.parentBranch ? (
                          <div className="text-xs text-muted-foreground">
                            parent {item.parentBranch}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap justify-end gap-2">
                        <Badge variant="secondary">{humanizeToken(item.status)}</Badge>
                        {item.prState ? (
                          <Badge variant="outline">PR {humanizeToken(item.prState)}</Badge>
                        ) : null}
                        {item.mergeGateStatus ? (
                          <Badge variant="outline">{humanizeToken(item.mergeGateStatus)}</Badge>
                        ) : null}
                        {item.reviewBlockingState && item.reviewBlockingState !== "clear" ? (
                          <Badge variant="outline">{humanizeToken(item.reviewBlockingState)}</Badge>
                        ) : null}
                        {item.isStale ? <Badge variant="outline">stale</Badge> : null}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 p-4">
            <div className="space-y-1">
              <div className="text-sm font-medium">
                {selectedTask ? selectedTask.title : "Run-level stack details"}
              </div>
              <div className="text-xs text-muted-foreground">
                {selectedTask ? selectedTask.taskId : run.runId}
              </div>
            </div>

            {selectedTask ? (
              <div className="space-y-4">
                <div className="space-y-2 rounded-2xl border bg-muted/20 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="secondary">{humanizeToken(selectedTask.status)}</Badge>
                        {selectedTask.taskPr ? (
                          <Badge variant="outline">
                            PR {humanizeToken(selectedTask.taskPr.state)}
                          </Badge>
                        ) : null}
                        {selectedTask.taskPr ? (
                          <Badge variant="outline">
                            {humanizeToken(selectedTask.taskPr.mergeGateStatus)}
                          </Badge>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                        <GitBranch className="h-4 w-4" />
                        <span>{selectedTask.taskPr?.headBranch ?? "branch pending"}</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                        <span>{selectedTask.taskPr?.baseBranch ?? selectedTask.parentBranch ?? run.featureBranch?.name ?? run.integrationBranch}</span>
                      </div>
                      {selectedTask.parentBranch ? (
                        <div className="text-xs text-muted-foreground">
                          parent branch {selectedTask.parentBranch}
                        </div>
                      ) : null}
                    </div>
                    {selectedTask.taskPr?.url ? (
                      <a
                        href={selectedTask.taskPr.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
                      >
                        <ExternalLink className="h-4 w-4" />
                        Open PR
                      </a>
                    ) : null}
                  </div>

                  {selectedTaskChecks.length > 0 ? (
                    <div className="grid gap-2 sm:grid-cols-2">
                      {selectedTaskChecks.map(([key, value]) => (
                        <div
                          key={key}
                          className="rounded-xl border border-border/70 bg-background px-3 py-2"
                        >
                          <div className="text-xs text-muted-foreground">
                            {humanizeToken(key)}
                          </div>
                          <div className="mt-1 text-sm font-medium">{String(value)}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      No checks snapshot recorded yet.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border bg-muted/20 p-4 text-sm text-muted-foreground">
                Select a task to inspect its task PR, checks, and merge history.
              </div>
            )}

            <div className="space-y-3">
              <div className="text-sm font-medium">
                {selectedTask ? "Selected task operation history" : "Run operation history"}
              </div>
              {viewModel.selectedOperationHistory.length === 0 ? (
                <div className="rounded-2xl border border-dashed p-4 text-sm text-muted-foreground">
                  No orchestration operations recorded yet.
                </div>
              ) : (
                <div className="space-y-3">
                  {viewModel.selectedOperationHistory.map((entry, index) => (
                    <div key={`${entry.kind}-${entry.startedAt}-${index}`} className="rounded-2xl border p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            {entry.status === "succeeded" ? (
                              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                            ) : (
                              <CircleAlert className="h-4 w-4 text-amber-500" />
                            )}
                            <span className="font-medium">{humanizeToken(entry.kind)}</span>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            started {new Date(entry.startedAt).toLocaleString()}
                          </div>
                          {entry.finishedAt ? (
                            <div className="text-xs text-muted-foreground">
                              finished {new Date(entry.finishedAt).toLocaleString()}
                            </div>
                          ) : null}
                          {entry.sessionId ? (
                            <div className="text-xs text-muted-foreground">
                              session <code>{entry.sessionId}</code>
                            </div>
                          ) : null}
                        </div>
                        <Badge variant="outline">{humanizeToken(entry.status)}</Badge>
                      </div>
                      {Object.keys(entry.details).length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {Object.entries(entry.details).map(([key, value]) => (
                            <Badge key={key} variant="outline">
                              {humanizeToken(key)} {String(value)}
                            </Badge>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
