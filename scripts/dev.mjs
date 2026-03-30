import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import {
  assertPortAvailableForCheckout,
  buildCheckoutInstance,
  buildDevChildEnv,
  ownsDevProcess,
} from "./dev-instance.mjs";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const checkoutInstance = buildCheckoutInstance(repoRoot, {
  apiPort:
    process.env.HELA_API_PORT === undefined
      ? undefined
      : Number.parseInt(process.env.HELA_API_PORT, 10),
  webPort:
    process.env.HELA_WEB_PORT === undefined
      ? undefined
      : Number.parseInt(process.env.HELA_WEB_PORT, 10),
});
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

function readProcessCwd(pid) {
  const output = runOutput("lsof", ["-a", "-p", String(pid), "-d", "cwd", "-Fn"]);
  const match = output.match(/\nn(.+)\s*$/);
  return match ? match[1].trim() : null;
}

function readProcessEnv(pid) {
  const output = runOutput("ps", ["eww", "-p", String(pid)]);
  if (!output) {
    return {};
  }
  const env = {};
  for (const match of output.matchAll(/(?:^|\s)([A-Z0-9_]+)=([^\s]+)/g)) {
    env[match[1]] = match[2];
  }
  return env;
}

function readProcessSnapshot(pid, port) {
  return {
    pid,
    port,
    cwd: readProcessCwd(pid),
    env: readProcessEnv(pid),
  };
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

function ensureCheckoutOwnedOrAvailable(port) {
  const pids = listListeningPids(port);
  if (pids.length === 0) {
    return [];
  }

  const owned = [];
  for (const pid of pids) {
    const snapshot = readProcessSnapshot(pid, port);
    assertPortAvailableForCheckout(checkoutInstance, snapshot);
    if (ownsDevProcess(checkoutInstance, snapshot)) {
      owned.push(pid);
    }
  }
  return owned;
}

function cleanupRepoProcesses() {
  const staleNextPids = listPidsHoldingFile(nextLockPath);
  if (staleNextPids.length > 0) {
    console.log(`[dev] stopping stale Next dev process(es): ${staleNextPids.join(", ")}`);
    terminatePids(staleNextPids);
  } else if (fs.existsSync(nextLockPath)) {
    fs.rmSync(nextLockPath, { force: true });
  }

  const staleApiPids = ensureCheckoutOwnedOrAvailable(checkoutInstance.apiPort);
  if (staleApiPids.length > 0) {
    console.log(`[dev] stopping stale FastAPI process(es): ${[...new Set(staleApiPids)].join(", ")}`);
    terminatePids(staleApiPids);
  }

  const staleWebPids = ensureCheckoutOwnedOrAvailable(checkoutInstance.webPort);
  if (staleWebPids.length > 0) {
    console.log(`[dev] stopping stale Next.js process(es): ${[...new Set(staleWebPids)].join(", ")}`);
    terminatePids(staleWebPids);
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

  const childEnv = buildDevChildEnv(checkoutInstance, process.env);

  console.log(`[dev] checkout ${checkoutInstance.checkoutId}`);
  console.log(`[dev] starting FastAPI on http://127.0.0.1:${checkoutInstance.apiPort}`);
  const api = spawnChild("api", "npm", ["run", "api:dev"], childEnv);
  children.push(api);

  console.log(`[dev] starting Next.js frontend on http://127.0.0.1:${checkoutInstance.webPort}`);
  const web = spawnChild("web", "npm", ["run", "dev:web"], childEnv);
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
