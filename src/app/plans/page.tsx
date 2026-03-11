"use client";

import Link from "next/link";
import { usePlans } from "@/hooks/use-plans";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText } from "lucide-react";

export default function PlansPage() {
  const { data: plans, isLoading } = usePlans();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Plans</h1>
        <p className="text-muted-foreground mt-1">
          Browse saved implementation plans
        </p>
      </div>

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
                    <div>
                      <p className="font-medium text-sm">{plan.title}</p>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {plan.preview}
                      </p>
                      <p className="text-xs text-muted-foreground mt-2 font-mono">
                        {plan.slug}
                      </p>
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
