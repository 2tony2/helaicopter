import { NextResponse } from "next/server";
import { getHistory } from "@/lib/claude-data";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = parseInt(searchParams.get("limit") || "100", 10);
  const history = await getHistory(limit);
  return NextResponse.json(history);
}
