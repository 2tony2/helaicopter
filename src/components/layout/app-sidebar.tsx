"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Braces,
  MessageSquare,
  FileText,
  BarChart3,
  DollarSign,
  Database,
  Network,
  Sparkles,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Analytics", icon: BarChart3 },
  { href: "/conversations", label: "Conversations", icon: MessageSquare },
  { href: "/orchestration", label: "Orchestration", icon: Network },
  { href: "/plans", label: "Plans", icon: FileText },
  { href: "/prompts", label: "Prompts", icon: Sparkles },
  { href: "/databases", label: "Databases", icon: Database },
  { href: "/docs", label: "Docs", icon: BookOpen },
  { href: "/pricing", label: "Pricing", icon: DollarSign },
];

const apiItems = [
  { href: "/schema", label: "API Explorer", icon: Braces },
  { href: "/openapi/helaicopter-api.json", label: "OpenAPI JSON" },
  { href: "/openapi/helaicopter-api.yaml", label: "OpenAPI YAML" },
];
const apiSection = { label: "API" };

export function AppSidebar({ onNavClick }: { onNavClick?: () => void } = {}) {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r bg-muted/30 min-h-screen flex flex-col">
      <div className="p-6 border-b">
        <h1 className="font-bold text-lg">Helaicopter</h1>
        <p className="text-xs text-muted-foreground mt-1">
          Conversation analytics viewer
        </p>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavClick}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
        <div className="px-3 pt-4 pb-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          {apiSection.label}
        </div>
        {apiItems.map((item) => {
          const isActive = item.href === "/schema" && pathname.startsWith("/schema");
          const linkClassName = cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
            isActive
              ? "bg-accent text-accent-foreground font-medium"
              : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
          );

          if (item.href.startsWith("/openapi/")) {
            return (
              <a
                key={item.href}
                href={item.href}
                className={linkClassName}
                download
              >
                {item.label}
              </a>
            );
          }

          return (
            <Link key={item.href} href={item.href} onClick={onNavClick} className={linkClassName}>
              {"icon" in item && item.icon ? <item.icon className="h-4 w-4" /> : null}
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
