import { redirect } from "next/navigation";

import { buildConversationRoute } from "@/lib/routes";

export default async function ConversationSubagentPage({
  params,
}: {
  params: Promise<{ projectPath: string; sessionId: string; agentId: string }>;
}) {
  const { projectPath, sessionId, agentId } = await params;

  redirect(
    buildConversationRoute(decodeURIComponent(projectPath), sessionId, {
      tab: "subagents",
      subagent: agentId,
    })
  );
}
