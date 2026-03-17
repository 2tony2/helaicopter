"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Bot, MessageSquare, Network, Router, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface ConversationDagNodeData {
  label: string;
  description?: string;
  nickname?: string;
  subagentType?: string;
  threadType: "main" | "subagent";
  hasTranscript: boolean;
  model?: string;
  messageCount: number;
  totalTokens: string;
  depth: number;
  isRoot: boolean;
  onClick: () => void;
}

export const ConversationDagNode = memo(function ConversationDagNode({
  data,
}: NodeProps) {
  const d = data as unknown as ConversationDagNodeData;

  return (
    <div
      className={cn(
        "nodrag w-[260px] rounded-2xl border-2 shadow-lg transition-all hover:shadow-xl hover:scale-[1.02] cursor-pointer",
        "bg-card text-card-foreground",
        d.isRoot
          ? "border-sky-500/60 dark:border-sky-400/50 ring-1 ring-sky-500/20"
          : "border-violet-500/50 dark:border-violet-400/40 ring-1 ring-violet-500/15"
      )}
      onClick={d.onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          d.onClick();
        }
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-muted-foreground !border-background !w-2.5 !h-2.5"
      />

      {/* Header */}
      <div
        className={cn(
          "rounded-t-[14px] px-4 py-3",
          d.isRoot
            ? "bg-sky-500/10 dark:bg-sky-500/15 border-b border-sky-500/20"
            : "bg-violet-500/10 dark:bg-violet-500/15 border-b border-violet-500/20"
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="line-clamp-2 text-sm font-semibold">
              {d.label}
            </div>
            {d.description && (
              <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                {d.description}
              </div>
            )}
          </div>
          <Badge
            className={cn(
              "shrink-0 capitalize border-0 font-medium",
              d.isRoot
                ? "bg-sky-500 text-white hover:bg-sky-600"
                : "bg-violet-500 text-white hover:bg-violet-600"
            )}
          >
            {d.threadType}
          </Badge>
        </div>
      </div>

      {/* Body */}
      <div className="space-y-3 px-4 py-3 text-xs">
        {(d.nickname || d.subagentType || d.model || !d.hasTranscript) && (
          <div className="flex items-center gap-2 flex-wrap">
            {d.nickname && (
              <Badge variant="outline" className="bg-muted/50">
                {d.nickname}
              </Badge>
            )}
            {d.subagentType && (
              <Badge variant="outline" className="bg-muted/50">
                {d.subagentType}
              </Badge>
            )}
            {d.model && (
              <Badge variant="outline" className="bg-muted/50">
                {d.model}
              </Badge>
            )}
            {!d.hasTranscript && (
              <Badge variant="outline" className="text-muted-foreground bg-muted/50">
                no transcript
              </Badge>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-2 text-muted-foreground">
          <div className="rounded-lg bg-muted/50 dark:bg-muted/30 px-2.5 py-2 border border-border/50">
            <div className="flex items-center gap-1.5">
              <MessageSquare className="h-3 w-3 text-emerald-500" />
              <span className="font-medium text-foreground/80">{d.messageCount}</span> msgs
            </div>
          </div>
          <div className="rounded-lg bg-muted/50 dark:bg-muted/30 px-2.5 py-2 border border-border/50">
            <div className="flex items-center gap-1.5">
              <Wrench className="h-3 w-3 text-amber-500" />
              <span className="font-medium text-foreground/80">{d.totalTokens}</span>
            </div>
          </div>
          <div className="rounded-lg bg-muted/50 dark:bg-muted/30 px-2.5 py-2 border border-border/50">
            <div className="flex items-center gap-1.5">
              <Network className="h-3 w-3 text-blue-500" />
              <span className="font-medium text-foreground/80">depth {d.depth}</span>
            </div>
          </div>
          <div
            className={cn(
              "rounded-lg px-2.5 py-2 border transition-colors",
              d.isRoot
                ? "bg-sky-500/10 border-sky-500/30 text-sky-600 dark:text-sky-400"
                : "bg-violet-500/10 border-violet-500/30 text-violet-600 dark:text-violet-400"
            )}
          >
            <div className="flex items-center gap-1.5">
              {d.isRoot ? <Bot className="h-3 w-3" /> : <Router className="h-3 w-3" />}
              <span className="font-medium">open thread</span>
            </div>
          </div>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-muted-foreground !border-background !w-2.5 !h-2.5"
      />
    </div>
  );
});
