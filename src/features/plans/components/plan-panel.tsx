"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { format } from "date-fns";
import { Download, Sparkles } from "lucide-react";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { PlanViewer } from "./plan-viewer";
import type { ConversationPlan, PlanDetail } from "@/lib/types";
import { cn, formatModelName, getModelBadgeClasses } from "@/lib/utils";
import { buildConversationTabRoute } from "@/lib/routes";

type PlanLike = ConversationPlan | PlanDetail;

function providerLabel(provider: "claude" | "codex"): string {
  return provider === "claude" ? "Claude" : "Codex";
}

function providerDotClass(provider: "claude" | "codex"): string {
  return provider === "claude" ? "bg-emerald-500" : "bg-sky-500";
}

function toFileHref(path: string): string {
  return encodeURI(`file://${path}`);
}

function downloadPlan(plan: PlanLike) {
  const blob = new Blob([plan.content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${plan.slug || "plan"}.md`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function MetadataValue({
  children,
  mono,
}: {
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div
      className={cn(
        "text-sm text-foreground min-w-0 break-all",
        mono && "font-mono text-xs"
      )}
    >
      {children}
    </div>
  );
}

export function PlanPanel({
  plan,
  extraActions,
  viewerClassName,
}: {
  plan: PlanLike;
  extraActions?: ReactNode;
  viewerClassName?: string;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">{plan.title}</h2>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="secondary" className="gap-2">
              <span
                className={cn("h-2 w-2 rounded-full", providerDotClass(plan.provider))}
              />
              {providerLabel(plan.provider)}
            </Badge>
            {plan.model ? (
              <Badge
                variant="outline"
                className={cn("text-xs", getModelBadgeClasses(plan.model))}
              >
                <Sparkles className="h-3 w-3 mr-1" />
                {formatModelName(plan.model)}
              </Badge>
            ) : (
              <Badge variant="outline" className="text-xs">
                <Sparkles className="h-3 w-3 mr-1" />
                unknown model
              </Badge>
            )}
            <span className="text-sm text-muted-foreground">
              {format(plan.timestamp, "MMM d, yyyy h:mm a")}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {extraActions}
          <Button variant="outline" size="sm" onClick={() => downloadPlan(plan)}>
            <Download className="h-4 w-4 mr-1.5" />
            Download
          </Button>
        </div>
      </div>

      <div className="grid gap-3 rounded-xl border bg-card p-4 md:grid-cols-2">
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Source file
          </div>
          <MetadataValue mono>
            {plan.sourcePath ? (
              <a
                href={toFileHref(plan.sourcePath)}
                className="hover:text-foreground underline underline-offset-4"
                title={plan.sourcePath}
              >
                {plan.sourcePath}
              </a>
            ) : (
              "none"
            )}
          </MetadataValue>
        </div>

        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Conversation
          </div>
          <MetadataValue mono>
            {plan.conversationRef ? (
              <Link
                href={buildConversationTabRoute(plan.conversationRef, "messages")}
                className="hover:text-foreground underline underline-offset-4"
              >
                {plan.projectPath && plan.sessionId
                  ? `${plan.projectPath}/${plan.sessionId}`
                  : plan.conversationRef}
              </Link>
            ) : (
              "none"
            )}
          </MetadataValue>
        </div>

        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Slug
          </div>
          <MetadataValue mono>{plan.slug}</MetadataValue>
        </div>

        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Provider
          </div>
          <MetadataValue>{providerLabel(plan.provider)}</MetadataValue>
        </div>
      </div>

      <PlanViewer content={plan.content} className={viewerClassName} />
    </div>
  );
}
