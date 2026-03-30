import crypto from "node:crypto";
import path from "node:path";

const API_PORT_BASE = 31000;
const WEB_PORT_BASE = 32000;
const PORT_SPAN = 2000;

function stableOffset(repoRoot) {
  const digest = crypto.createHash("sha1").update(path.resolve(repoRoot)).digest("hex");
  return {
    digest,
    offset: Number.parseInt(digest.slice(0, 8), 16) % PORT_SPAN,
  };
}

export function buildCheckoutInstance(repoRoot, overrides = {}) {
  const normalizedRoot = path.resolve(repoRoot);
  const { digest, offset } = stableOffset(normalizedRoot);
  const apiPort = overrides.apiPort ?? API_PORT_BASE + offset;
  const webPort = overrides.webPort ?? WEB_PORT_BASE + offset;

  return {
    repoRoot: normalizedRoot,
    checkoutId: digest.slice(0, 12),
    apiPort,
    webPort,
  };
}

export function buildDevChildEnv(instance, baseEnv) {
  const apiHost = baseEnv.HELA_API_HOST || "127.0.0.1";
  const webHost = baseEnv.HELA_WEB_HOST || "127.0.0.1";
  const useApiProxy = baseEnv.HELA_USE_API_PROXY === "1";

  return {
    ...baseEnv,
    HELA_CHECKOUT_ID: instance.checkoutId,
    HELA_PROJECT_ROOT: instance.repoRoot,
    HELA_API_PORT: String(instance.apiPort),
    HELA_API_HOST: apiHost,
    HELA_WEB_PORT: String(instance.webPort),
    HELA_WEB_HOST: webHost,
    HELA_USE_API_PROXY: useApiProxy ? "1" : "",
    PORT: String(instance.webPort),
    NEXT_PUBLIC_API_BASE_URL: useApiProxy ? "" : `http://127.0.0.1:${instance.apiPort}`,
  };
}

export function ownsDevProcess(instance, snapshot = {}) {
  if (!snapshot || typeof snapshot !== "object") {
    return false;
  }
  const env = snapshot.env && typeof snapshot.env === "object" ? snapshot.env : {};
  const cwd = typeof snapshot.cwd === "string" ? path.resolve(snapshot.cwd) : null;

  if (env.HELA_CHECKOUT_ID === instance.checkoutId) {
    return true;
  }
  if (env.HELA_PROJECT_ROOT && path.resolve(env.HELA_PROJECT_ROOT) === instance.repoRoot) {
    return true;
  }
  return cwd === instance.repoRoot;
}

export function assertPortAvailableForCheckout(instance, occupant) {
  if (!occupant) {
    return;
  }
  if (ownsDevProcess(instance, occupant)) {
    return;
  }
  throw new Error(
    `Port ${occupant.port ?? instance.apiPort} is occupied by a different checkout (pid ${occupant.pid ?? "unknown"}).`
  );
}
