import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CredentialList } from "./credential-list";
import type { AuthCredential } from "@/lib/types";

function buildCredential(
  overrides: Partial<AuthCredential>
): AuthCredential {
  return {
    credentialId: "cred_default",
    provider: "claude",
    credentialType: "local_cli_session",
    status: "active",
    providerStatusCode: "ready",
    providerStatusMessage: "Credential is ready for provider execution.",
    tokenExpiresAt: null,
    cliConfigPath: "/tmp/.claude",
    subscriptionId: null,
    subscriptionTier: null,
    rateLimitTier: null,
    createdAt: "2026-03-26T09:00:00Z",
    lastUsedAt: null,
    lastRefreshedAt: null,
    cumulativeCostUsd: 0,
    costSinceReset: 0,
    ...overrides,
  };
}

test("CredentialList only renders refresh actions for oauth credentials", () => {
  const markup = renderToStaticMarkup(
    <CredentialList
      credentials={[
        buildCredential({
          credentialId: "cred_claude",
          provider: "claude",
          credentialType: "local_cli_session",
        }),
        buildCredential({
          credentialId: "cred_codex",
          provider: "codex",
          credentialType: "oauth_token",
          tokenExpiresAt: "2026-04-01T00:00:00Z",
        }),
      ]}
    />
  );

  const claudeSection = markup.split("cred_claude")[1]?.split("cred_codex")[0] ?? "";
  const codexSection = markup.split("cred_codex")[1] ?? "";

  assert.equal((markup.match(/Refresh auth/g) ?? []).length, 1);
  assert.doesNotMatch(claudeSection, /Refresh auth/);
  assert.match(codexSection, /Refresh auth/);
});
