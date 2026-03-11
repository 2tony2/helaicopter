"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  FileText,
  BarChart3,
  DollarSign,
  Database,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Analytics", icon: BarChart3 },
  { href: "/conversations", label: "Conversations", icon: MessageSquare },
  { href: "/plans", label: "Plans", icon: FileText },
  { href: "/schema", label: "Schema", icon: Database },
  { href: "/pricing", label: "Pricing", icon: DollarSign },
];

export function AppSidebar() {
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
      </nav>
    </aside>
  );
}
