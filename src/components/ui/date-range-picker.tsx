"use client";

import { cn } from "@/lib/utils";

const presets = [
  { label: "7d", days: 7 },
  { label: "14d", days: 14 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "All", days: undefined },
] as const;

export function DateRangePicker({
  value,
  onChange,
}: {
  value: number | undefined;
  onChange: (days: number | undefined) => void;
}) {
  return (
    <div className="inline-flex items-center rounded-lg border bg-muted p-1 text-muted-foreground">
      {presets.map((preset) => (
        <button
          key={preset.label}
          onClick={() => onChange(preset.days)}
          className={cn(
            "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-colors",
            value === preset.days
              ? "bg-background text-foreground shadow"
              : "hover:bg-background/50 hover:text-foreground"
          )}
        >
          {preset.label}
        </button>
      ))}
    </div>
  );
}
