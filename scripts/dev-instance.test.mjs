import assert from "node:assert/strict";
import test from "node:test";

import {
  assertPortAvailableForCheckout,
  buildCheckoutInstance,
  buildDevChildEnv,
  ownsDevProcess,
} from "./dev-instance.mjs";

test("buildCheckoutInstance is stable for one repo root", () => {
  const a = buildCheckoutInstance("/Users/tony/Code/helaicopter");
  const b = buildCheckoutInstance("/Users/tony/Code/helaicopter");

  assert.equal(a.checkoutId, b.checkoutId);
  assert.equal(a.apiPort, b.apiPort);
  assert.equal(a.webPort, b.webPort);
});

test("buildCheckoutInstance differs across sibling checkouts", () => {
  const a = buildCheckoutInstance("/Users/tony/Code/helaicopter");
  const b = buildCheckoutInstance("/Users/tony/Code/helaicopter-main");

  assert.notEqual(a.checkoutId, b.checkoutId);
  assert.notEqual(a.apiPort, b.apiPort);
  assert.notEqual(a.webPort, b.webPort);
});

test("buildDevChildEnv stamps checkout ownership metadata", () => {
  const instance = buildCheckoutInstance("/Users/tony/Code/helaicopter");
  const env = buildDevChildEnv(instance, {});

  assert.equal(env.HELA_CHECKOUT_ID, instance.checkoutId);
  assert.equal(env.HELA_PROJECT_ROOT, "/Users/tony/Code/helaicopter");
  assert.equal(env.HELA_API_PORT, String(instance.apiPort));
  assert.equal(env.PORT, String(instance.webPort));
  assert.equal(env.NEXT_PUBLIC_API_BASE_URL, `http://127.0.0.1:${instance.apiPort}`);
});

test("cleanup ignores a process owned by another checkout", () => {
  const current = buildCheckoutInstance("/repo/a");
  const foreign = buildCheckoutInstance("/repo/b");

  assert.equal(
    ownsDevProcess(current, {
      HELA_CHECKOUT_ID: foreign.checkoutId,
      HELA_PROJECT_ROOT: "/repo/b",
    }),
    false
  );
});

test("startup rejects an occupied derived port when owner metadata does not match", () => {
  assert.throws(
    () =>
      assertPortAvailableForCheckout(
        { apiPort: 31123, checkoutId: "aaaa", repoRoot: "/repo/a" },
        { pid: 999, env: { HELA_CHECKOUT_ID: "bbbb", HELA_PROJECT_ROOT: "/repo/b" } }
      ),
    /occupied by a different checkout/
  );
});
