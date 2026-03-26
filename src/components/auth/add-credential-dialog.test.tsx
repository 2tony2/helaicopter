import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CredentialProviderActions } from "./add-credential-dialog";

test("CredentialProviderActions shows provider-aware Claude and Codex actions without API key fields", () => {
  const markup = renderToStaticMarkup(<CredentialProviderActions />);

  assert.match(markup, /Reuse Claude CLI session/);
  assert.match(markup, /OAuth redirect/);
  assert.doesNotMatch(markup, /API key/i);
  assert.doesNotMatch(markup, /Save API key/i);
});
