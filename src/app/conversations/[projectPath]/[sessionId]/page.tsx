"use client";

import { use } from "react";
import { ConversationViewer } from "@/components/conversation/conversation-viewer";
import { projectDirToDisplayName } from "@/lib/path-encoding";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";

export default function ConversationPage({
  params,
}: {
  params: Promise<{ projectPath: string; sessionId: string }>;
}) {
  const { projectPath, sessionId } = use(params);
  const decodedPath = decodeURIComponent(projectPath);
  const displayName = projectDirToDisplayName(decodedPath);

  return (
    <div className="space-y-8">
      <Breadcrumbs
        items={[
          { href: "/conversations", label: "Conversations" },
          { label: <span title={decodedPath} className="truncate max-w-xs inline-block">{displayName}</span> },
          { label: <span className="font-mono text-xs">{sessionId.slice(0, 8)}...</span> },
        ]}
      />

      <ConversationViewer projectPath={decodedPath} sessionId={sessionId} />
    </div>
  );
}
