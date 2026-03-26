import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { Worker } from "@/lib/types";

function formatTimestamp(value?: string | null) {
  if (!value) {
    return "unknown";
  }

  return new Date(value).toLocaleString();
}

export function WorkerCard({
  worker,
  onDrain,
  onRemove,
  onResetSession,
  pendingAction,
}: {
  worker: Worker;
  onDrain?: (workerId: string) => void;
  onRemove?: (workerId: string) => void;
  onResetSession?: (workerId: string) => void;
  pendingAction?: string | null;
}) {
  const isPending = pendingAction === worker.workerId;
  const showReset = worker.sessionResetAvailable;

  return (
    <Card className="border-border/60">
      <CardContent className="space-y-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="font-medium">{worker.workerId}</div>
            <div className="text-sm text-muted-foreground">
              {worker.workerType} on {worker.host}
            </div>
          </div>
          <Badge variant="outline">{worker.status}</Badge>
        </div>

        <div className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
          <div>
            <div className="font-medium text-foreground">Current task</div>
            <div>{worker.currentTaskId ?? "unassigned"}</div>
          </div>
          <div>
            <div className="font-medium text-foreground">Current run</div>
            <div>{worker.currentRunId ?? "idle"}</div>
          </div>
          <div>
            <div className="font-medium text-foreground">Heartbeat</div>
            <div>{formatTimestamp(worker.lastHeartbeatAt)}</div>
          </div>
          <div>
            <div className="font-medium text-foreground">Capabilities</div>
            <div>{worker.capabilities.models.join(", ") || "none"}</div>
          </div>
          <div>
            <div className="font-medium text-foreground">Session</div>
            <div>{`session ${worker.sessionStatus}`}</div>
          </div>
          <div>
            <div className="font-medium text-foreground">Session last used</div>
            <div>{formatTimestamp(worker.sessionLastUsedAt)}</div>
          </div>
          <div>
            <div className="font-medium text-foreground">Discovery</div>
            <div>{worker.capabilities.supportsDiscovery ? "enabled" : "disabled"}</div>
          </div>
          <div>
            <div className="font-medium text-foreground">Tags</div>
            <div>{worker.capabilities.tags.join(", ") || "none"}</div>
          </div>
        </div>

        {worker.readinessReason ? (
          <div className="rounded-lg border border-amber-400/40 bg-amber-500/5 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
            {worker.readinessReason}
          </div>
        ) : null}

        {worker.sessionFailureReason ? (
          <div className="rounded-lg border border-rose-400/40 bg-rose-500/5 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">
            {worker.sessionFailureReason}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={isPending}
            onClick={() => onDrain?.(worker.workerId)}
          >
            Drain worker
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={isPending}
            onClick={() => onRemove?.(worker.workerId)}
          >
            Remove worker
          </Button>
          {showReset ? (
            <Button
              variant="outline"
              size="sm"
              disabled={isPending}
              onClick={() => onResetSession?.(worker.workerId)}
            >
              Reset session
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
