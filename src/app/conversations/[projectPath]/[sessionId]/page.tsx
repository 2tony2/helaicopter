"use client";

import { use } from "react";
import { ConversationViewer } from "@/components/conversation/conversation-viewer";
import { projectDirToDisplayName } from "@/lib/path-encoding";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { resolveConversationDetailTab } from "@/lib/routes";

export default function ConversationPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectPath: string; sessionId: string }>;
  searchParams: Promise<{ tab?: string; plan?: string; subagent?: string; message?: string }>;
}) {
  const { projectPath, sessionId } = use(params);
  const { tab, plan, subagent, message } = use(searchParams);
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

      <ConversationViewer
        projectPath={decodedPath}
        sessionId={sessionId}
        initialTab={resolveConversationDetailTab(tab)}
        initialPlanId={plan}
        initialSubagentId={subagent}
        initialMessageId={message}
      />
    </div>
  );
}
