"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ReactNode } from "react";

export function StatsCard({
  title,
  value,
  description,
  icon,
  accentColor,
}: {
  title: string;
  value: string | number;
  description?: string;
  icon?: ReactNode;
  accentColor?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-1.5 truncate">
          {icon && <span style={accentColor ? { color: accentColor } : undefined} className={accentColor ? "flex-shrink-0" : "text-muted-foreground flex-shrink-0"}>{icon}</span>}
          <span className="truncate">{title}</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className="text-2xl font-bold tabular-nums tracking-tight truncate"
          style={accentColor ? { color: accentColor } : undefined}
        >
          {value}
        </div>
        {description && (
          <p className="text-xs text-muted-foreground mt-1 tabular-nums">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}
