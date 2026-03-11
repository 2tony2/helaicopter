"use client";

import { use } from "react";
import Link from "next/link";
import { format } from "date-fns";
import { usePlan } from "@/hooks/use-plans";
import { PlanViewer } from "@/components/plans/plan-viewer";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ChevronRight } from "lucide-react";

function providerLabel(provider: "claude" | "codex"): string {
  return provider === "claude" ? "Claude" : "Codex";
}

export default function PlanDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug: planId } = use(params);
  const { data: plan, isLoading } = usePlan(planId);

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link href="/plans" className="hover:text-foreground transition-colors">
          Plans
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-foreground">{plan?.title ?? plan?.slug ?? "Plan"}</span>
      </nav>

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : plan ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="secondary">{providerLabel(plan.provider)}</Badge>
            <span className="text-sm text-muted-foreground">
              {format(plan.timestamp, "MMM d, yyyy h:mm a")}
            </span>
            {plan.projectPath && plan.sessionId && (
              <Link
                href={`/conversations/${encodeURIComponent(plan.projectPath)}/${plan.sessionId}`}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Open conversation
              </Link>
            )}
          </div>
          <PlanViewer content={plan.content} />
        </div>
      ) : (
        <p className="text-muted-foreground">Plan not found</p>
      )}
    </div>
  );
}
