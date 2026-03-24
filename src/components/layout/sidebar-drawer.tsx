"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { useSidebar } from "./sidebar-provider";
import { AppSidebar } from "./app-sidebar";

export function SidebarDrawer() {
  const { open, close } = useSidebar();
  const pathname = usePathname();

  // Close drawer on route change
  useEffect(() => {
    close();
  }, [pathname, close]);

  // Handle Escape key
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, close]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={close}
        aria-hidden="true"
      />
      {/* Drawer panel */}
      <div className="fixed inset-y-0 left-0 w-64 shadow-xl">
        <div className="relative h-full">
          <button
            type="button"
            onClick={close}
            className="absolute right-2 top-2 z-10 inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-accent"
            aria-label="Close navigation menu"
          >
            <X className="h-4 w-4" />
          </button>
          <AppSidebar onNavClick={close} />
        </div>
      </div>
    </div>
  );
}
