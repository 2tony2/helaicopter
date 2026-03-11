"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { TokenUsageBadge } from "./token-usage-badge";
import { ThinkingBlock } from "./thinking-block";
import { ToolCallBlock } from "./tool-call-block";
import type { ProcessedMessage } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MessageCard({
  message,
  provider,
}: {
  message: ProcessedMessage;
  provider?: "claude" | "codex";
}) {
  const isUser = message.role === "user";

  return (
    <Card
      className={`p-4 ${
        isUser
          ? "border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20"
          : "border-border"
      }`}
    >
      <div className="flex items-center gap-2 mb-3">
        <Badge variant={isUser ? "default" : "secondary"}>
          {isUser ? "User" : "Assistant"}
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
