"use client";

import { use } from "react";
import { usePlan } from "@/hooks/use-plans";
import { PlanPanel } from "@/components/plans/plan-panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";

export default function PlanDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug: planId } = use(params);
  const { data: plan, isLoading } = usePlan(planId);

  return (
    <div className="space-y-8">
      <Breadcrumbs
        items={[
          { href: "/plans", label: "Plans" },
          { label: plan?.title ?? plan?.slug ?? "Plan" },
        ]}
      />

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : plan ? (
        <PlanPanel
          plan={plan}
          viewerClassName="h-[calc(100vh-18rem)] min-h-[420px]"
        />
      ) : (
        <p className="text-muted-foreground">Plan not found</p>
      )}
    </div>
  );
}
