import { NextResponse } from "next/server";
import { readDatabaseStatus, runDatabaseRefresh } from "@/lib/database-refresh";

export async function GET() {
  let status = await readDatabaseStatus();

  if (!status) {
    status = await runDatabaseRefresh({
      force: true,
      trigger: "bootstrap",
    });
  }

  return NextResponse.json(status);
}
