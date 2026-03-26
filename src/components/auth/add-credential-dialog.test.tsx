import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CredentialProviderActions, AddCredentialDialog } from "./add-credential-dialog";
import { AuthManagementSection } from "./auth-management-section";
import type { AuthCredential } from "@/lib/types";

function findByText(node: React.ReactNode, text: string): React.ReactElement | null {
  if (!React.isValidElement(node)) {
    return null;
  }

  const children = node.props.children;
  const directText = typeof children === "string" ? children : null;
  if (directText === text) {
    return node;
  }

  const childArray = React.Children.toArray(children);
  for (const child of childArray) {
    const match = findByText(child, text);
    if (match) {
      return match;
    }
  }

  return null;
}

function findByType(node: React.ReactNode, type: React.ElementType): React.ReactElement | null {
  if (!React.isValidElement(node)) {
    return null;
  }

  if (node.type === type) {
    return node;
  }

  const childArray = React.Children.toArray(node.props.children);
  for (const child of childArray) {
    const match = findByType(child, type);
    if (match) {
      return match;
    }
  }

  return null;
}

function buildCredential(): AuthCredential {
  return {
    credentialId: "cred_claude_active",
    provider: "claude",
    credentialType: "api_key",
    status: "active",
    providerStatusCode: "ready",
    providerStatusMessage: "Credential is ready for provider execution.",
    tokenExpiresAt: "2026-04-01T00:00:00Z",
    cliConfigPath: null,
    subscriptionId: null,
    subscriptionTier: null,
    rateLimitTier: "pro",
    createdAt: "2026-03-20T08:00:00Z",
    lastUsedAt: "2026-03-26T09:00:00Z",
    lastRefreshedAt: null,
    cumulativeCostUsd: 2.5,
    costSinceReset: 1.25,
  };
}

test("CredentialProviderActions invokes the Claude and Codex callbacks", () => {
  let claudeConnectCount = 0;
  let oauthProvider: AuthCredential["provider"] | null = null;

  const tree = CredentialProviderActions({
    onConnectClaudeCli: () => {
      claudeConnectCount += 1;
    },
    onOauth: (provider) => {
      oauthProvider = provider;
    },
  });

  const claudeButton = findByText(tree, "Reuse Claude CLI session");
  assert.ok(claudeButton);
  claudeButton!.props.onClick();
  assert.equal(claudeConnectCount, 1);

  const codexButton = findByText(tree, "OAuth redirect");
  assert.ok(codexButton);
  codexButton!.props.onClick();
  assert.equal(oauthProvider, "codex");
});

test("AuthManagementSection passes provider-aware actions through to the add-credential dialog", () => {
  const onConnectClaudeCli = () => undefined;
  const onInitiateOauth = () => undefined;
  const tree = AuthManagementSection({
    credentials: [buildCredential()],
    onConnectClaudeCli,
    onInitiateOauth,
  });

  const dialog = findByType(tree, AddCredentialDialog);
  assert.ok(dialog);
  assert.equal(dialog!.props.onConnectClaudeCli, onConnectClaudeCli);
  assert.equal(dialog!.props.onOauth, onInitiateOauth);
});

test("CredentialProviderActions shows provider-aware Claude and Codex actions without API key fields", () => {
  const markup = renderToStaticMarkup(<CredentialProviderActions />);

  assert.match(markup, /Reuse Claude CLI session/);
  assert.match(markup, /OAuth redirect/);
  assert.doesNotMatch(markup, /API key/i);
  assert.doesNotMatch(markup, /Save API key/i);
});
