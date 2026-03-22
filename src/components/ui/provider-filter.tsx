"use client";

import type { FrontendProvider } from "@/lib/types";
import { cn } from "@/lib/utils";

export type Provider = "all" | FrontendProvider;

export const providerFilterOptions: { value: Provider; label: string }[] = [
  { value: "all", label: "All" },
  { value: "claude", label: "Claude" },
  { value: "codex", label: "Codex" },
  { value: "openclaw", label: "OpenClaw" },
];

export function ProviderFilter({
  value,
  onChange,
}: {
  value: Provider;
  onChange: (v: Provider) => void;
}) {
  return (
    <div className="inline-flex items-center rounded-md border bg-muted/50 p-0.5">
      {providerFilterOptions.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            "px-3 py-1 text-xs font-medium rounded-sm transition-colors",
            value === opt.value
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
