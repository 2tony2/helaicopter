import { NextResponse } from "next/server";
import { runDatabaseRefresh } from "@/lib/database-refresh";

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const force = Boolean(body.force);
  const trigger = typeof body.trigger === "string" ? body.trigger : "manual";

  const status = await runDatabaseRefresh({
    force,
    trigger,
    staleAfterSeconds: 21_600,
  });

  return NextResponse.json(status);
}
