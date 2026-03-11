import { NextResponse } from "next/server";
import { listProjects } from "@/lib/claude-data";

export async function GET() {
  const projects = await listProjects();
  return NextResponse.json(projects);
}
