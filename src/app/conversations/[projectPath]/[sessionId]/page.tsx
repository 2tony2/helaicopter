"use client";

import { use } from "react";
import Link from "next/link";
import { ConversationViewer } from "@/components/conversation/conversation-viewer";
import { ChevronRight } from "lucide-react";
import { projectDirToDisplayName } from "@/lib/path-encoding";

export default function ConversationPage({
  params,
}: {
  params: Promise<{ projectPath: string; sessionId: string }>;
}) {
  const { projectPath, sessionId } = use(params);
  const decodedPath = decodeURIComponent(projectPath);
  const displayName = projectDirToDisplayName(decodedPath);

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link href="/conversations" className="hover:text-foreground transition-colors">
          Conversations
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="truncate max-w-xs" title={decodedPath}>
          {displayName}
        </span>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-foreground font-mono text-xs">
          {sessionId.slice(0, 8)}...
        </span>
      </nav>

      <ConversationViewer projectPath={decodedPath} sessionId={sessionId} />
    </div>
  );
}
