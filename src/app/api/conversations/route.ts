import { NextResponse } from "next/server";
import { listConversations } from "@/lib/claude-data";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const project = searchParams.get("project") || undefined;
  const daysParam = searchParams.get("days");
  const days = daysParam ? parseInt(daysParam, 10) : undefined;
  const conversations = await listConversations(project, days);
  return NextResponse.json(conversations);
}
