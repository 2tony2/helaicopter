"use client";

import { useState } from "react";
import { ChevronRight, Terminal, AlertCircle } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { DisplayToolCallBlock } from "@/lib/types";

type ToolResultSection = {
  label: string;
  value: string;
  multiline: boolean;
};

function inputPreview(input: Record<string, unknown>): string {
  const keys = Object.keys(input);
  if (keys.length === 0) return "";

  // Show the most meaningful field as preview
  const previewKey =
    keys.find((k) => ["command", "file_path", "pattern", "query", "url", "content"].includes(k)) ||
    keys[0];
  const val = input[previewKey];
  const str = typeof val === "string" ? val : JSON.stringify(val);
  return str.slice(0, 80) + (str.length > 80 ? "..." : "");
}

function titleize(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function stringifyResultValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null) return "null";
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2);
}

function parseResultJson(result: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(result);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

export function formatToolResultSections(result: string): ToolResultSection[] {
  const parsed = parseResultJson(result);
  if (!parsed) {
    return [{ label: "Result", value: result, multiline: result.includes("\n") || result.length > 120 }];
  }

  const keys = Object.keys(parsed).filter((key) => {
    const value = parsed[key];
    return value !== undefined && value !== null && !(Array.isArray(value) && value.length === 0);
  });
  const preferred = ["success", "name", "description", "path", "readiness_status", "setup_needed"];
  const contentKeys = ["content", "stdout", "stderr", "output", "result"];
  const ordered = [
    ...preferred.filter((key) => keys.includes(key)),
    ...keys.filter((key) => !preferred.includes(key) && !contentKeys.includes(key)),
    ...contentKeys.filter((key) => keys.includes(key)),
  ];

  return ordered.map((key) => {
    const value = stringifyResultValue(parsed[key]);
    return {
      label: key === "success" ? "Status" : titleize(key),
      value: key === "success" && parsed[key] === true ? "success" : value,
      multiline: value.includes("\n") || value.length > 120 || typeof parsed[key] === "object",
    };
  });
}

function ToolResultSections({ result, isError }: { result: string; isError?: boolean | null }) {
  const sections = formatToolResultSections(result);
  return (
    <div className="space-y-2">
      {sections.map((section) => (
        <div key={section.label} className="rounded-md border bg-muted/30">
          <div className="border-b px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {section.label}
          </div>
          {section.multiline ? (
            <pre
              className={`p-3 text-xs leading-5 whitespace-pre-wrap overflow-x-auto ${
                isError ? "text-destructive" : ""
              }`}
            >
              {section.value}
            </pre>
          ) : (
            <div className={`px-3 py-2 text-sm ${isError ? "text-destructive" : ""}`}>
              {section.value}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function ToolCallBlock({ block }: { block: DisplayToolCallBlock }) {
  const [open, setOpen] = useState(false);
  const preview = inputPreview(block.input);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center gap-2 text-sm hover:bg-muted/50 rounded-md px-2 py-1.5 transition-colors cursor-pointer w-full text-left">
        <ChevronRight
          className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
        />
        <Terminal className="h-4 w-4 shrink-0 text-muted-foreground" />
        <Badge variant="secondary" className="text-xs shrink-0">
          {block.toolName}
        </Badge>
        {block.isError && (
          <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0" />
        )}
        <span className="text-muted-foreground truncate text-xs font-mono">
          {preview}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent forceMount>
        <div className="ml-6 mt-1 space-y-2">
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">Input</div>
            <ScrollArea className="max-h-64">
              <pre className="text-xs bg-muted/50 rounded-md p-3 font-mono whitespace-pre-wrap overflow-x-auto">
                {JSON.stringify(block.input, null, 2)}
              </pre>
            </ScrollArea>
          </div>
          {block.result !== undefined && (
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">
                Result {block.isError && <span className="text-destructive">(error)</span>}
              </div>
              <ScrollArea className="max-h-64">
                <ToolResultSections result={block.result} isError={block.isError} />
              </ScrollArea>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
