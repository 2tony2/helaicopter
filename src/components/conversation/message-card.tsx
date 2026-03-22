"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { TokenUsageBadge } from "./token-usage-badge";
import { ThinkingBlock } from "./thinking-block";
import { ToolCallBlock } from "./tool-call-block";
import type { FrontendProvider, ProcessedMessage } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";
import { Link as LinkIcon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

export function MessageCard({
  message,
  provider,
  href,
  isSelected = false,
  onSelect,
}: {
  message: ProcessedMessage;
  provider?: FrontendProvider;
  href?: string;
  isSelected?: boolean;
  onSelect?: () => void;
}) {
  const isUser = message.role === "user";

  return (
    <Card
      id={`message-${message.id}`}
      className={`p-4 ${
        isUser
          ? "border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20"
          : "border-border"
      } ${isSelected ? "ring-2 ring-primary/40 border-primary/60" : ""}`}
    >
      <div className="flex items-center gap-2 mb-3">
        <Badge variant={isUser ? "default" : "secondary"}>
          {isUser ? "User" : "Assistant"}
        </Badge>
        <Badge variant="outline" className="font-mono text-[10px]">
          {message.id.slice(0, 8)}
        </Badge>
        {message.model && (
          <Badge variant="outline" className="text-xs">
            {message.model.replace("claude-", "").replace(/-\d+$/, "")}
          </Badge>
        )}
        <TokenUsageBadge
          usage={message.usage}
          model={message.model}
          reasoningTokens={message.reasoningTokens}
          provider={provider}
        />
        {message.speed === "fast" && (
          <Badge variant="outline" className="text-xs text-amber-600 dark:text-amber-400 border-amber-300 dark:border-amber-600">
            fast
          </Badge>
        )}
        <span className="text-xs text-muted-foreground ml-auto">
          {formatDistanceToNow(message.timestamp, { addSuffix: true })}
        </span>
        {href ? (
          <Link
            href={href}
            onClick={onSelect}
            className={cn(
              "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-foreground",
              isSelected ? "border-primary/50 text-primary" : ""
            )}
          >
            <LinkIcon className="h-3 w-3" />
            Link
          </Link>
        ) : null}
      </div>

      <div className="space-y-3">
        {message.blocks.map((block, i) => {
          switch (block.type) {
            case "text":
              return (
                <div key={i} className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {block.text}
                  </ReactMarkdown>
                </div>
              );
            case "thinking":
              return <ThinkingBlock key={i} block={block} />;
            case "tool_call":
              return <ToolCallBlock key={i} block={block} />;
            default:
              return null;
          }
        })}
      </div>
    </Card>
  );
}
