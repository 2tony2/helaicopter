import { NextResponse } from "next/server";
import { conversationListResponseCache } from "@/lib/cache";
import { queryConversationSummaries } from "@/lib/conversation-summary-query-backend";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const project = searchParams.get("project") || undefined;
  const daysParam = searchParams.get("days");
  const days = daysParam ? parseInt(daysParam, 10) : undefined;
  const cacheKey = JSON.stringify({
    project: project ?? null,
    days: days ?? null,
  });
  const conversations = await conversationListResponseCache.getOrLoad(
    cacheKey,
    5_000,
    () => queryConversationSummaries(project, days)
  );
  const response = NextResponse.json(conversations);
  response.headers.set("x-conversations-cache", "memory");
  return response;
}
