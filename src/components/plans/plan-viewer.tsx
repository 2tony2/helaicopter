"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

export function PlanViewer({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  return (
    <ScrollArea
      className={cn(
        "h-[420px] min-h-[320px] rounded-xl border bg-muted/20",
        className
      )}
    >
      <div className="prose prose-sm dark:prose-invert max-w-none p-4">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </ScrollArea>
  );
}
