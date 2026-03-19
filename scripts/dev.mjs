import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const apiPort = process.env.HELA_API_PORT ?? "30000";
const nextLockPath = path.join(repoRoot, ".next", "dev", "lock");

function runOutput(command, args) {
  try {
    return execFileSync(command, args, {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch (error) {
    if (error && typeof error === "object" && "stdout" in error) {
      return String(error.stdout ?? "").trim();
    }
    return "";
  }
}

function listPidsHoldingFile(filePath) {
  const output = runOutput("lsof", ["-t", filePath]);
  return output
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function listListeningPids(port) {
  const output = runOutput("lsof", ["-tiTCP:" + port, "-sTCP:LISTEN"]);
  return output
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function listMatchingPids(pattern) {
  const output = runOutput("pgrep", ["-f", pattern]);
  return output
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function childPids(pid) {
  const output = runOutput("pgrep", ["-P", String(pid)]);
  return output
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function collectProcessTree(rootPid, seen = new Set()) {
  if (seen.has(rootPid)) {
    return [];
  }
  seen.add(rootPid);
  const descendants = childPids(rootPid).flatMap((pid) => collectProcessTree(pid, seen));
  return [...descendants, rootPid];
}

function terminatePids(pids) {
  const unique = [...new Set(pids.flatMap((pid) => collectProcessTree(pid)))];
  for (const pid of unique) {
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      // Ignore already-exited processes.
    }
  }
}

function cleanupRepoProcesses() {
  const staleNextPids = listPidsHoldingFile(nextLockPath);
  if (staleNextPids.length > 0) {
    console.log(`[dev] stopping stale Next dev process(es): ${staleNextPids.join(", ")}`);
    terminatePids(staleNextPids);
  } else if (fs.existsSync(nextLockPath)) {
    fs.rmSync(nextLockPath, { force: true });
  }

  const staleApiPids = [
    ...listListeningPids(apiPort),
    ...listMatchingPids("uvicorn .*helaicopter_api\\.server\\.main:app"),
  ];
  if (staleApiPids.length > 0) {
    console.log(`[dev] stopping stale FastAPI process(es): ${[...new Set(staleApiPids)].join(", ")}`);
    terminatePids(staleApiPids);
  }
}

function spawnChild(name, command, args, env = process.env) {
  const child = spawn(command, args, {
    cwd: repoRoot,
    env,
    stdio: "inherit",
  });
  child.on("error", (error) => {
    console.error(`[dev] ${name} failed to start:`, error);
  });
  return child;
}

function main() {
  cleanupRepoProcesses();

  if (process.env.HELA_SKIP_PREFECT_BOOTSTRAP !== "1") {
    // Default bootstrap entrypoint: bin/oats-prefect-up
    console.log("[dev] bootstrapping Prefect control plane and worker");
    execFileSync(path.join(repoRoot, "bin", "oats-prefect-up"), [], {
      cwd: repoRoot,
      stdio: "inherit",
      env: process.env,
    });
  }

  const children = [];
  let shuttingDown = false;

  const shutdown = (code = 0) => {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    for (const child of children) {
      if (!child.killed) {
        try {
          child.kill("SIGTERM");
        } catch {
          // Ignore already-exited children.
        }
      }
    }
    setTimeout(() => process.exit(code), 200);
  };

  process.on("SIGINT", () => shutdown(0));
  process.on("SIGTERM", () => shutdown(0));

  const webEnv = {
    ...process.env,
    NEXT_PUBLIC_API_BASE_URL:
      process.env.NEXT_PUBLIC_API_BASE_URL ?? `http://127.0.0.1:${apiPort}`,
  };

  console.log(`[dev] starting FastAPI on http://127.0.0.1:${apiPort}`);
  const api = spawnChild("api", "npm", ["run", "api:dev"]);
  children.push(api);

  console.log("[dev] starting Next.js frontend");
  const web = spawnChild("web", "npm", ["run", "dev:web"], webEnv);
  children.push(web);

  for (const child of children) {
    child.on("exit", (code, signal) => {
      if (shuttingDown) {
        return;
      }
      if (signal) {
        console.log(`[dev] child exited with signal ${signal}`);
        shutdown(1);
        return;
      }
      if (code && code !== 0) {
        console.log(`[dev] child exited with code ${code}`);
        shutdown(code);
      }
    });
  }
}

main();
