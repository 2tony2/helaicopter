"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export type Crumb = { label: React.ReactNode; href?: string };

export function Breadcrumbs({
  items,
  className,
}: {
  items: Crumb[];
  className?: string;
}) {
  return (
    <nav className={cn("flex items-center gap-1.5 text-sm text-muted-foreground", className)}>
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        const content = item.href && !isLast ? (
          <Link href={item.href} className="hover:text-foreground transition-colors">
            {item.label}
          </Link>
        ) : (
          <span className={cn(isLast && "text-foreground")}>{item.label}</span>
        );
        return (
          <React.Fragment key={i}>
            {i > 0 ? <ChevronRight className="h-3.5 w-3.5" /> : null}
            {content}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
