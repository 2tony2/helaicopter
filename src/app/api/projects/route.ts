import { NextResponse } from "next/server";
import { projectListResponseCache } from "@/lib/cache";
import { listProjects } from "@/lib/claude-data";

export async function GET() {
  const projects = await projectListResponseCache.getOrLoad(
    "projects",
    15_000,
    () => listProjects()
  );
  const response = NextResponse.json(projects);
  response.headers.set("x-projects-cache", "memory");
  return response;
}
