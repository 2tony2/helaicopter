import { NextResponse } from "next/server";
import { conversationDagResponseCache } from "@/lib/cache";
import { buildConversationDag } from "@/lib/conversation-dag";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ projectPath: string; sessionId: string }> }
) {
  const { projectPath, sessionId } = await params;
  const decodedProjectPath = decodeURIComponent(projectPath);
  const cacheKey = JSON.stringify({
    projectPath: decodedProjectPath,
    sessionId,
  });

  const dag = await conversationDagResponseCache.getOrLoad(
    cacheKey,
    5_000,
    () => buildConversationDag(decodedProjectPath, sessionId)
  );

  if (!dag) {
    return NextResponse.json({ error: "Conversation DAG not found" }, { status: 404 });
  }

  return NextResponse.json(dag);
}
