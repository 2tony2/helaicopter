"use client";

import Link from "next/link";
import { format } from "date-fns";
import { FileText } from "lucide-react";
import { usePlans } from "@/features/plans/hooks/use-plans";
import { PageHeader } from "@/shared/layout/page-header";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { formatModelName, getModelBadgeClasses } from "@/lib/utils";

function providerLabel(provider: "claude" | "codex"): string {
  return provider === "claude" ? "Claude" : "Codex";
}

function providerDotClass(provider: "claude" | "codex"): string {
  return provider === "claude" ? "bg-emerald-500" : "bg-sky-500";
}

export function PlansIndexView() {
  const { data: plans, isLoading } = usePlans();

  return (
    <div className="space-y-8">
      <PageHeader
        title="Plans"
        description="Browse saved implementation plans"
      />

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {plans?.map((plan) => (
            <Link key={plan.id} href={`/plans/${plan.id}`}>
              <Card className="h-full cursor-pointer transition-colors hover:bg-accent/50">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium">{plan.title}</p>
                        <Badge
                          variant="secondary"
                          className="shrink-0 gap-1.5 text-[10px]"
                        >
                          <span
                            className={`h-2 w-2 rounded-full ${providerDotClass(plan.provider)}`}
                          />
                          {providerLabel(plan.provider)}
                        </Badge>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                        {plan.preview}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
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
                      <div className="mt-2 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                        <p className="truncate font-mono">{plan.slug}</p>
                        <span className="shrink-0">
                          {format(plan.timestamp, "MMM d")}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
          {plans?.length === 0 ? (
            <p className="col-span-2 py-8 text-center text-muted-foreground">
              No plans found
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
