import { NextResponse } from "next/server";
import { queryConversationSummaries } from "@/lib/conversation-summary-query-backend";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const project = searchParams.get("project") || undefined;
  const daysParam = searchParams.get("days");
  const days = daysParam ? parseInt(daysParam, 10) : undefined;
  const conversations = await queryConversationSummaries(project, days);
  return NextResponse.json(conversations);
}
