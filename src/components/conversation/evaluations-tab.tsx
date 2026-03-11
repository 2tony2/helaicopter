"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { format } from "date-fns";
import { Bot, Clock3, Loader2, TriangleAlert } from "lucide-react";
import type { ConversationEvaluation } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function EvaluationsTab({
  evaluations,
}: {
  evaluations: ConversationEvaluation[];
}) {
  if (evaluations.length === 0) {
    return (
      <p className="mt-4 text-sm text-muted-foreground">
        No evaluations have been run for this conversation yet.
      </p>
    );
  }

  return (
    <div className="mt-4 space-y-4">
      {evaluations.map((evaluation) => (
        <Card key={evaluation.evaluationId}>
          <CardHeader className="space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <CardTitle className="text-base">{evaluation.promptName}</CardTitle>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant={evaluation.status === "failed" ? "destructive" : "secondary"}>
                  {evaluation.status}
                </Badge>
                <Badge variant="outline">{evaluation.provider}</Badge>
                <Badge variant="outline">{evaluation.model}</Badge>
              </div>
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
              <div className="flex items-center gap-1">
                <Clock3 className="h-3.5 w-3.5" />
                {format(new Date(evaluation.createdAt), "MMM d, yyyy h:mm:ss a")}
              </div>
              <div>Scope: {evaluation.scope.replace(/_/g, " ")}</div>
              {evaluation.durationMs ? <div>{(evaluation.durationMs / 1000).toFixed(1)}s</div> : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {evaluation.selectionInstruction && (
              <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                <div className="mb-1 font-medium">Selection Instruction</div>
                <div className="text-muted-foreground">{evaluation.selectionInstruction}</div>
              </div>
            )}

            {evaluation.errorMessage ? (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                <div className="mb-1 flex items-center gap-2 font-medium">
                  <TriangleAlert className="h-4 w-4" />
                  Evaluation Failed
                </div>
                <div>{evaluation.errorMessage}</div>
              </div>
            ) : null}

            {evaluation.status === "running" ? (
              <div className="rounded-lg border bg-muted/40 p-4 text-sm">
                <div className="flex items-center gap-2 font-medium">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  report generating in background...
                </div>
              </div>
            ) : null}

            {evaluation.reportMarkdown ? (
              <div className="rounded-lg border p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium">
                  <Bot className="h-4 w-4" />
                  Evaluation Report
                </div>
                <div className="prose prose-sm max-w-none whitespace-pre-wrap dark:prose-invert">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {evaluation.reportMarkdown}
                  </ReactMarkdown>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
