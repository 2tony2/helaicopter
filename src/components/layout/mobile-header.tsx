"use client";

import { Menu } from "lucide-react";
import { useSidebar } from "./sidebar-provider";

export function MobileHeader({ className }: { className?: string }) {
  const { toggle } = useSidebar();

  return (
    <header
      className={`sticky top-0 z-40 flex items-center gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/60 ${className ?? ""}`}
      style={{ paddingTop: `max(0.75rem, env(safe-area-inset-top))` }}
    >
      <button
        type="button"
        onClick={toggle}
        className="inline-flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
        aria-label="Toggle navigation menu"
      >
        <Menu className="h-5 w-5" />
      </button>
      <span className="text-sm font-semibold">Helaicopter</span>
    </header>
  );
}
