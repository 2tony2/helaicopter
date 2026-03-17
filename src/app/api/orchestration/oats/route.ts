import { NextResponse } from "next/server";
import { listOvernightOatsRuns } from "@/lib/orchestration-data";

export async function GET() {
  return NextResponse.json(await listOvernightOatsRuns());
}
