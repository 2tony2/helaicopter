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
      <CollapsibleContent>
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
                <pre
                  className={`text-xs rounded-md p-3 font-mono whitespace-pre-wrap overflow-x-auto ${
                    block.isError
                      ? "bg-destructive/10 text-destructive"
                      : "bg-muted/50"
                  }`}
                >
                  {block.result}
                </pre>
              </ScrollArea>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
