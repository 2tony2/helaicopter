import { NextResponse } from "next/server";
import { listPlans } from "@/lib/claude-data";

export async function GET() {
  const plans = await listPlans();
  return NextResponse.json(plans);
}
