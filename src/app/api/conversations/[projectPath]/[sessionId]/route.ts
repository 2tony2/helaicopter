import { NextResponse } from "next/server";
import { getConversation } from "@/lib/claude-data";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ projectPath: string; sessionId: string }> }
) {
  const { projectPath, sessionId } = await params;
  const decoded = decodeURIComponent(projectPath);
  const conversation = await getConversation(decoded, sessionId);

  if (!conversation) {
    return NextResponse.json(
      { error: "Conversation not found" },
      { status: 404 }
    );
  }

  return NextResponse.json(conversation);
}
