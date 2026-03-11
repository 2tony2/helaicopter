"use client";

import { cn } from "@/lib/utils";

export type Provider = "all" | "claude" | "codex";

export function ProviderFilter({
  value,
  onChange,
}: {
  value: Provider;
  onChange: (v: Provider) => void;
}) {
  const options: { value: Provider; label: string }[] = [
    { value: "all", label: "All" },
    { value: "claude", label: "Claude" },
    { value: "codex", label: "Codex" },
  ];

  return (
    <div className="inline-flex items-center rounded-md border bg-muted/50 p-0.5">
      {options.map((opt) => (
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
