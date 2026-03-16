import { NextResponse } from "next/server";
import { queryAnalytics } from "@/lib/analytics-query-backend";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const daysParam = searchParams.get("days");
  const days = daysParam ? parseInt(daysParam, 10) : undefined;
  const provider = searchParams.get("provider") || undefined;
  const analytics = await queryAnalytics(days, provider);
  return NextResponse.json(analytics);
}
