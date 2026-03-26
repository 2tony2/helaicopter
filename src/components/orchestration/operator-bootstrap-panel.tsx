"use client";

import { CheckCircle2, CircleAlert, Cpu, KeyRound, ServerCog } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useOperatorBootstrap } from "@/lib/client/operator-bootstrap";
import type { OperatorBootstrapSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

function ChecklistItem({
  done,
  label,
}: {
  done: boolean;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {done ? (
        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
      ) : (
        <CircleAlert className="h-4 w-4 text-amber-500" />
      )}
      <span>{label}</span>
    </div>
  );
}

function NextStepHint({ nextStep }: { nextStep?: string | null }) {
  if (!nextStep) {
    return null;
  }

  return <div className="mt-1 text-xs text-muted-foreground">Next: {nextStep}</div>;
}

export function OperatorBootstrapPanel({ summary }: { summary: OperatorBootstrapSummary }) {
  return (
    <section id="operator-bootstrap" className="space-y-4 scroll-mt-24">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">Bootstrap Checklist</h2>
          <p className="text-sm text-muted-foreground">
            What still needs attention before the operator flow is healthy.
          </p>
        </div>
        <div
          className={cn(
            "rounded-lg border px-3 py-2 text-sm font-medium",
            summary.overallStatus === "ready"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
              : "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300"
          )}
        >
          {summary.overallStatus}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Resolver</div>
            <div className="mt-2 flex items-center gap-2 text-sm font-medium">
              <ServerCog className="h-4 w-4 text-sky-500" />
              {summary.resolverRunning ? "Running" : "Not running"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Workers</div>
            <div className="mt-2 flex items-center gap-2 text-sm font-medium">
              <Cpu className="h-4 w-4 text-sky-500" />
              {summary.totalWorkerCount}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Credentials</div>
            <div className="mt-2 flex items-center gap-2 text-sm font-medium">
              <KeyRound className="h-4 w-4 text-sky-500" />
              {summary.totalCredentialCount}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="font-medium">Operator checklist</div>
          <ChecklistItem done={summary.hasClaudeWorker} label="Start a Claude worker" />
          <ChecklistItem done={summary.hasCodexWorker} label="Start a Codex worker" />
          <ChecklistItem done={summary.resolverRunning} label="Backend resolver loop running" />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="font-medium">Provider readiness</div>
          {summary.providers.map((provider) => (
            <div key={provider.provider} className="rounded-lg border border-border/60 px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div className="font-medium">{provider.provider}</div>
                <div className="text-muted-foreground">{provider.status}</div>
              </div>
              <div className="text-muted-foreground">
                {provider.workerCount} workers · {provider.credentialCount} credentials
              </div>
              {provider.blockingReasons[0] ? (
                <div className="mt-1 text-amber-800 dark:text-amber-300">
                  {provider.blockingReasons[0].message}
                  <NextStepHint nextStep={provider.blockingReasons[0].nextStep} />
                </div>
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>

      {summary.blockingReasons.length > 0 ? (
        <Card>
          <CardContent className="space-y-3 p-4">
            <div className="font-medium">Blocking reasons</div>
            {summary.blockingReasons.map((reason) => (
              <div
                key={reason.code}
                className="rounded-lg border border-amber-400/40 bg-amber-500/5 px-3 py-2 text-sm text-amber-800 dark:text-amber-300"
              >
                <div>{reason.message}</div>
                <NextStepHint nextStep={reason.nextStep} />
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}

export function OperatorBootstrapPanelContainer() {
  const { data, isLoading } = useOperatorBootstrap();

  if (isLoading && !data) {
    return <Skeleton className="h-48 w-full" />;
  }

  if (!data) {
    return null;
  }

  return <OperatorBootstrapPanel summary={data} />;
}
