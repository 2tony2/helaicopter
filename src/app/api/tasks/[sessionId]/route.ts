import { NextResponse } from "next/server";
import { getTasksForSession } from "@/lib/claude-data";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params;
  const tasks = await getTasksForSession(sessionId);
  return NextResponse.json(tasks);
}
