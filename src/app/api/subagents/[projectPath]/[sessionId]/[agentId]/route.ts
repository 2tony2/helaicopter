import { NextResponse } from "next/server";
import { getSubagentConversation } from "@/lib/claude-data";

export async function GET(
  _request: Request,
  {
    params,
  }: {
    params: Promise<{
      projectPath: string;
      sessionId: string;
      agentId: string;
    }>;
  }
) {
  const { projectPath, sessionId, agentId } = await params;
  const decoded = decodeURIComponent(projectPath);
  const conversation = await getSubagentConversation(
    decoded,
    sessionId,
    agentId
  );

  if (!conversation) {
    return NextResponse.json(
      { error: "Subagent conversation not found" },
      { status: 404 }
    );
  }

  return NextResponse.json(conversation);
}
