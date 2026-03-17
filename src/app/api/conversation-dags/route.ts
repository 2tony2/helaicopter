import { NextResponse } from "next/server";
import { conversationDagResponseCache } from "@/lib/cache";
import { listConversationDagSummaries } from "@/lib/conversation-dag";
import type { SupportedProvider } from "@/lib/types";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const project = searchParams.get("project") || undefined;
  const daysParam = searchParams.get("days");
  const days = daysParam ? parseInt(daysParam, 10) : undefined;
  const providerParam = searchParams.get("provider");
  const provider =
    providerParam === "claude" || providerParam === "codex"
      ? (providerParam as SupportedProvider)
      : undefined;

  const cacheKey = JSON.stringify({
    project: project ?? null,
    days: days ?? null,
    provider: provider ?? null,
  });

  const conversations = await conversationDagResponseCache.getOrLoad(
    cacheKey,
    5_000,
    () => listConversationDagSummaries(project, days, provider)
  );

  return NextResponse.json(conversations);
}
