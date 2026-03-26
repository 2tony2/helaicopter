"use client";

import { useMemo, type ReactNode } from "react";
import { Activity, ShieldAlert, Skull, Waves, Wrench } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDrainWorker, useRemoveWorker, useWorkers } from "@/lib/client/workers";
import type { Worker } from "@/lib/types";
import { WorkerCard } from "./worker-card";

type WorkerSummary = {
  total: number;
  idle: number;
  busy: number;
  draining: number;
  dead: number;
  authExpired: number;
};

type WorkerProviderGroup = {
  provider: Worker["provider"];
  workers: Worker[];
};

export function buildWorkerDashboardModel(workers: Worker[]) {
  const sorted = [...workers].sort((a, b) =>
    a.provider === b.provider
      ? a.workerId.localeCompare(b.workerId)
      : a.provider.localeCompare(b.provider)
  );

  const providerGroups = sorted.reduce<WorkerProviderGroup[]>((groups, worker) => {
    const current = groups[groups.length - 1];
    if (current && current.provider === worker.provider) {
      current.workers.push(worker);
      return groups;
    }
    groups.push({ provider: worker.provider, workers: [worker] });
    return groups;
  }, []);

  const summary = sorted.reduce<WorkerSummary>(
    (acc, worker) => {
      acc.total += 1;
      if (worker.status === "idle") acc.idle += 1;
      if (worker.status === "busy") acc.busy += 1;
      if (worker.status === "draining") acc.draining += 1;
      if (worker.status === "dead") acc.dead += 1;
      if (worker.status === "auth_expired") acc.authExpired += 1;
      return acc;
    },
    { total: 0, idle: 0, busy: 0, draining: 0, dead: 0, authExpired: 0 }
  );

  return {
    summary,
    providerGroups,
    hasAuthIssues: summary.authExpired > 0,
  };
}

function SummaryCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: ReactNode;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
          {icon}
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

export function WorkerDashboardSection({
  workers,
  onDrain,
  onRemove,
  pendingAction,
  error,
}: {
  workers: Worker[];
  onDrain?: (workerId: string) => void;
  onRemove?: (workerId: string) => void;
  pendingAction?: string | null;
  error?: string | null;
}) {
  const dashboard = buildWorkerDashboardModel(workers);

  return (
    <section id="worker-dashboard" className="space-y-4 scroll-mt-24">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">Worker Dashboard</h2>
          <p className="text-sm text-muted-foreground">
            Long-lived workers grouped by provider, with direct drain and removal controls.
          </p>
        </div>
        {dashboard.hasAuthIssues ? (
          <div className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
            auth_expired workers need credential refresh before they can dispatch.
          </div>
        ) : null}
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <SummaryCard label="Workers" value={dashboard.summary.total} icon={<Wrench className="h-5 w-5 text-sky-500" />} />
        <SummaryCard label="Idle" value={dashboard.summary.idle} icon={<Activity className="h-5 w-5 text-emerald-500" />} />
        <SummaryCard label="Busy" value={dashboard.summary.busy} icon={<Waves className="h-5 w-5 text-blue-500" />} />
        <SummaryCard label="Dead" value={dashboard.summary.dead} icon={<Skull className="h-5 w-5 text-rose-500" />} />
        <SummaryCard label="Auth Issues" value={dashboard.summary.authExpired} icon={<ShieldAlert className="h-5 w-5 text-amber-500" />} />
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-400/40 bg-rose-500/5 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="space-y-6">
        {dashboard.providerGroups.map((group) => (
          <div key={group.provider} className="space-y-3">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {group.provider}
              </h3>
              <span className="text-xs text-muted-foreground">
                {group.workers.length} worker{group.workers.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              {group.workers.map((worker) => (
                <WorkerCard
                  key={worker.workerId}
                  worker={worker}
                  onDrain={onDrain}
                  onRemove={onRemove}
                  pendingAction={pendingAction}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function WorkerDashboardPanel() {
  const { data: workers, isLoading } = useWorkers();
  const drain = useDrainWorker();
  const remove = useRemoveWorker();
  const pendingAction = drain.pendingWorkerId ?? remove.pendingWorkerId;
  const error = drain.error ?? remove.error;
  const items = useMemo(() => workers ?? [], [workers]);

  if (isLoading && items.length === 0) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-32 w-full" />
        ))}
      </div>
    );
  }

  return (
    <WorkerDashboardSection
      workers={items}
      onDrain={(workerId) => void drain.run(workerId)}
      onRemove={(workerId) => void remove.run(workerId)}
      pendingAction={pendingAction}
      error={error}
    />
  );
}
