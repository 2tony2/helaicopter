"use client";

import { use } from "react";
import Link from "next/link";
import { usePlan } from "@/hooks/use-plans";
import { PlanViewer } from "@/components/plans/plan-viewer";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronRight } from "lucide-react";

export default function PlanDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const { data: plan, isLoading } = usePlan(slug);

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link href="/plans" className="hover:text-foreground transition-colors">
          Plans
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-foreground">{slug}</span>
      </nav>

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : plan ? (
        <PlanViewer content={plan.content} />
      ) : (
        <p className="text-muted-foreground">Plan not found</p>
      )}
    </div>
  );
}
