# Codex CLI Reuse Instead Of OAuth

## Goal

Replace the current Codex app-managed OAuth flow with local Codex CLI session reuse so provider auth "just works" the same way Claude does.

The target outcome is a local-only operator flow where:

- `claude auth status` can be reused into a Claude credential
- `codex login status` can be reused into a Codex credential
- the orchestration UI shows both providers as ready without any browser OAuth redirect
- Pi workers use the already-authenticated local CLIs for real execution

## Why Change

The current Codex path is mismatched to the actual user expectation and local environment:

- the machine already has a valid local Codex login
- the app-managed OAuth flow requires a client id we do not currently ship
- even with a client id, the callback UX is awkward because it lands on a backend JSON endpoint

This makes Codex feel broken even though the local CLI is already authenticated. Reusing the local CLI session matches how the user expects OpenClaw-style auth to behave and removes a whole class of setup friction.

## Recommended Approach

Use local CLI reuse for both providers:

- Claude remains `local_cli_session`
- Codex changes from `oauth_token` to `local_cli_session`

The auth management UI becomes explicitly CLI-based:

- `Reuse Claude CLI session`
- `Reuse Codex CLI session`

No browser OAuth redirect should remain in the primary operator flow.

## API Changes

### New or Retained Connect Endpoints

- Keep `POST /auth/credentials/claude-cli/connect`
- Add `POST /auth/credentials/codex-cli/connect`

Both endpoints should:

- validate the local CLI auth state
- create or reuse one active `local_cli_session` credential for that provider
- return actionable `400` errors when the CLI is missing or not logged in

### OAuth Cleanup

Codex OAuth should be removed from the normal product flow.

There are two acceptable cleanup levels:

1. Preferred: remove Codex OAuth routes, settings, and UI entirely.
2. Transitional: keep backend OAuth code dormant for now, but remove all frontend/operator entry points and readiness assumptions that depend on it.

The user-facing flow should not mention OAuth anymore.

## Validation Rules

### Claude

Continue validating with:

- `claude auth status`

Keep the current hardened rules:

- empty success output is invalid
- malformed JSON fallback output is invalid
- filesystem fallback is only a last resort

### Codex

Validate with:

- `codex login status`

Success should require meaningful login output such as "Logged in".

Failure cases should produce actionable guidance such as:

- run `codex login`
- verify the Codex CLI is installed

## Credential Model

Both providers should persist as `local_cli_session`.

Required behavior:

- reuse an existing active credential when possible
- revoke or replace duplicate active credentials for the same provider
- do not expose refresh actions for CLI-backed credentials

## Provider Readiness

`provider_readiness` should expect `local_cli_session` for:

- `claude`
- `codex`

Missing-auth messages should become:

- Claude: local Claude CLI session missing
- Codex: local Codex CLI session missing

There should be no OAuth-specific readiness wording left for Codex.

## UI Changes

### Auth Management

Replace the current Claude/Codex action pair with:

- `Reuse Claude CLI session`
- `Reuse Codex CLI session`

Remove:

- Codex `OAuth redirect`
- any user-facing Codex OAuth error copy
- any suggestion that Codex credentials can be refreshed via backend token refresh

### Bootstrap And Worker Views

All readiness and remediation messaging should refer to local CLI sessions for both providers.

## Testing

Update and extend tests for:

- Codex CLI connect endpoint
- Codex duplicate credential reuse/replacement
- provider readiness expecting `local_cli_session` for Codex
- auth management rendering CLI actions for both providers
- removal of OAuth-only Codex UI paths

Smoke verification should prove:

1. `claude auth status` valid -> Claude connect succeeds
2. `codex login status` valid -> Codex connect succeeds
3. orchestration bootstrap becomes provider-ready for both
4. Pi workers dispatch with both providers using local CLI auth

## Success Criteria

The change is complete when:

- Codex no longer requires app OAuth setup
- the UI no longer presents a Codex OAuth redirect
- both providers can become ready from local CLI auth alone
- operator flow is simpler and matches the user's expectation of "just works"
