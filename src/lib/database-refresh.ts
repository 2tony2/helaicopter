import { access, readFile } from "fs/promises";
import { join } from "path";
import { promisify } from "util";
import { execFile } from "child_process";
import type { DatabaseStatus } from "@/lib/types";

const execFileAsync = promisify(execFile);

export const DATABASE_STATUS_PATH = join(
  process.cwd(),
  "var",
  "database-runtime",
  "status.json"
);

export async function readDatabaseStatus(): Promise<DatabaseStatus | null> {
  try {
    await access(DATABASE_STATUS_PATH);
    const raw = await readFile(DATABASE_STATUS_PATH, "utf-8");
    const status = JSON.parse(raw) as Partial<DatabaseStatus>;
    if (!status.runtime || !status.databases?.clickhouse || !status.databases?.sqlite) {
      return null;
    }
    return status as DatabaseStatus;
  } catch {
    return null;
  }
}

export async function runDatabaseRefresh({
  force = false,
  trigger = "manual",
  staleAfterSeconds = 21_600,
}: {
  force?: boolean;
  trigger?: string;
  staleAfterSeconds?: number;
} = {}): Promise<DatabaseStatus> {
  const args = [
    "run",
    "python",
    "-m",
    "helaicopter_db.refresh",
    "--trigger",
    trigger,
    "--stale-after-seconds",
    String(staleAfterSeconds),
  ];

  if (force) {
    args.push("--force");
  }

  const { stdout } = await execFileAsync("uv", args, {
    cwd: process.cwd(),
    maxBuffer: 20 * 1024 * 1024,
  });

  const lines = stdout
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const payload = lines.at(-1);
  if (!payload) {
    throw new Error("Database refresh did not return a status payload.");
  }

  return JSON.parse(payload) as DatabaseStatus;
}
