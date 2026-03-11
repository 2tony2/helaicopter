"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { DisplayThinkingBlock } from "@/lib/types";

export function ThinkingBlock({ block }: { block: DisplayThinkingBlock }) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer py-1">
        <ChevronRight
          className={`h-4 w-4 transition-transform ${open ? "rotate-90" : ""}`}
        />
        <span className="italic">Thinking</span>
        <span className="text-xs opacity-60">
          ({(block.charCount / 1000).toFixed(1)}K chars)
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ScrollArea className="max-h-96 mt-2">
          <pre className="text-sm text-muted-foreground whitespace-pre-wrap bg-muted/50 rounded-lg p-4 font-mono">
            {block.thinking}
          </pre>
        </ScrollArea>
      </CollapsibleContent>
    </Collapsible>
  );
}
