"use client";

import Link from "next/link";
import { format } from "date-fns";
import { usePlans } from "@/hooks/use-plans";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { FileText } from "lucide-react";
import { formatModelName, getModelBadgeClasses } from "@/lib/utils";
import { PageHeader } from "@/components/layout/page-header";

function providerLabel(provider: "claude" | "codex"): string {
  return provider === "claude" ? "Claude" : "Codex";
}

function providerDotClass(provider: "claude" | "codex"): string {
  return provider === "claude" ? "bg-emerald-500" : "bg-sky-500";
}

export default function PlansPage() {
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {plans?.map((plan) => (
            <Link key={plan.id} href={`/plans/${plan.id}`}>
              <Card className="hover:bg-accent/50 transition-colors cursor-pointer h-full">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <FileText className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium text-sm">{plan.title}</p>
                        <Badge variant="secondary" className="text-[10px] shrink-0 gap-1.5">
                          <span
                            className={`h-2 w-2 rounded-full ${providerDotClass(plan.provider)}`}
                          />
                          {providerLabel(plan.provider)}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {plan.preview}
                      </p>
                      <div className="mt-2 flex items-center gap-2 flex-wrap">
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
                        <p className="font-mono truncate">{plan.slug}</p>
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
          {plans?.length === 0 && (
            <p className="text-muted-foreground col-span-2 text-center py-8">
              No plans found
            </p>
          )}
        </div>
      )}
    </div>
  );
}
