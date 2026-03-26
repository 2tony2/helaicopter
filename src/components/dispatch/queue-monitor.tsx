"use client";

import { Clock3, History, ListTodo } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useDispatchHistory,
  useDispatchQueue,
} from "@/lib/client/dispatch";
import type { DispatchHistoryEntry, DispatchQueueSnapshot } from "@/lib/types";

export function QueueMonitorSection({
  snapshot,
  history,
}: {
  snapshot: DispatchQueueSnapshot;
  history: DispatchHistoryEntry[];
}) {
  return (
    <section id="queue-monitor" className="space-y-4 scroll-mt-24">
      <div>
        <h2 className="text-xl font-semibold">Queue Monitor</h2>
        <p className="text-sm text-muted-foreground">
          Ready queue depth, deferred dispatch reasons, and recent dispatches.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Ready</div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <ListTodo className="h-5 w-5 text-sky-500" />
              {snapshot.ready.length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Deferred</div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <Clock3 className="h-5 w-5 text-amber-500" />
              {snapshot.deferred.length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Recent dispatches
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <History className="h-5 w-5 text-violet-500" />
              {history.length}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardContent className="space-y-3 p-4">
            <div className="font-medium">Ready queue</div>
            {snapshot.ready.length === 0 ? (
              <div className="text-sm text-muted-foreground">No tasks are ready to dispatch.</div>
            ) : (
              snapshot.ready.map((entry) => (
                <div
                  key={`${entry.runId}:${entry.taskId}`}
                  className="rounded-lg border border-border/60 px-3 py-2 text-sm"
                >
                  <div className="font-medium">{entry.taskId}</div>
                  <div className="text-muted-foreground">
                    {entry.runId} · {entry.provider} · {entry.model}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3 p-4">
            <div className="font-medium">Deferred queue</div>
            {snapshot.deferred.length === 0 ? (
              <div className="text-sm text-muted-foreground">No tasks are deferred.</div>
            ) : (
              snapshot.deferred.map((entry) => (
                <div
                  key={`${entry.runId}:${entry.taskId}:${entry.reason}`}
                  className="rounded-lg border border-border/60 px-3 py-2 text-sm"
                >
                  <div className="font-medium">{entry.taskId}</div>
                  <div className="text-muted-foreground">
                    {entry.runId} · {entry.provider} · {entry.reason}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="font-medium">Recent dispatches</div>
          {history.length === 0 ? (
            <div className="text-sm text-muted-foreground">No dispatches recorded yet.</div>
          ) : (
            history.map((entry) => (
              <div
                key={`${entry.workerId}:${entry.taskId}:${entry.dispatchedAt}`}
                className="rounded-lg border border-border/60 px-3 py-2 text-sm"
              >
                <div className="font-medium">
                  {entry.taskId} → {entry.workerId}
                </div>
                <div className="text-muted-foreground">
                  {entry.runId} · {entry.provider} · {entry.model} · {entry.dispatchedAt}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </section>
  );
}

export function QueueMonitorPanel() {
  const { data: snapshot, isLoading: queueLoading } = useDispatchQueue();
  const { data: history, isLoading: historyLoading } = useDispatchHistory();

  if ((queueLoading || historyLoading) && (!snapshot || !history)) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 2 }).map((_, index) => (
          <Skeleton key={index} className="h-28 w-full" />
        ))}
      </div>
    );
  }

  return (
    <QueueMonitorSection
      snapshot={snapshot ?? { ready: [], deferred: [] }}
      history={history ?? []}
    />
  );
}
