# Provider Auth: Real Claude CLI Reuse and Codex OAuth

## Goal

Turn Helaicopter's auth layer from provider-readiness plumbing into real, usable provider authentication for the two providers we actually care about:

- `claude` via local Claude CLI session reuse
- `codex` via real local-only OAuth with PKCE and localhost callback

This intentionally does **not** add Anthropic API-key auth. The user explicitly does not want API keys for Claude.

## Desired Outcome

After this work:

- the auth management UI offers a real provider-specific action for both providers
- Claude can become runnable by reusing an already-authenticated local Claude CLI session
- Codex can become runnable by completing a real OAuth redirect and token exchange
- bootstrap/provider-readiness surfaces report actual auth state instead of placeholder configuration gaps
- worker dispatch for Claude and Codex can be blocked or enabled by real credential state

## Non-Goals

- remote/VPS OAuth support
- Anthropic browser OAuth
- Anthropic API-key flows
- broad provider-auth plugin abstraction
- reworking the orchestration model beyond the auth entry points needed here

## Why This Shape

OpenClaw's current provider split is the right model to copy:

- Anthropic/Claude is treated as API key, setup-token, or Claude CLI reuse
- OpenAI Codex is treated as real OAuth

For Helaicopter, the closest fit to the product goal is:

- Claude: reuse local CLI auth already present on the operator machine
- Codex: use browser OAuth and persist refreshable tokens in Helaicopter

That keeps the local operator flow realistic without fabricating OAuth for Claude.

## Approach Options Considered

### 1. Hybrid auth matching OpenClaw

- Claude via local CLI reuse
- Codex via OAuth

Pros:

- matches the real provider capabilities we found
- aligns with user preference
- avoids API keys for Claude
- keeps Codex UX better than raw CLI-state scraping

Cons:

- two provider-specific auth flows instead of one generic mechanism

### 2. All CLI reuse

- Claude and Codex both use local CLI session reuse

Pros:

- simplest backend flow

Cons:

- worse Codex UX
- more coupled to local CLI state layouts
- skips the real OAuth path the user prefers for Codex

### 3. Generic auth-plugin framework first

Pros:

- cleanest architecture on paper

Cons:

- delays the actual feature again
- adds abstraction before we have two real working provider clients

### Recommendation

Choose option 1.

## Architecture

### Claude auth path

Claude becomes a real `local_cli_session` provider credential.

The backend discovers and validates a local Claude CLI session by checking local Claude auth state on the same machine that runs Helaicopter. Validation should prefer a direct CLI status probe when available and fall back to local config/session inspection when needed.

The operator action is not OAuth. Instead, the backend exposes an explicit connect/reuse flow that materializes a `local_cli_session` credential for provider `claude`.

That credential should persist:

- `provider = "claude"`
- `credential_type = "local_cli_session"`
- `cli_config_path`
- optional subscription or account metadata if discoverable
- active/revoked status like other credentials

Provider readiness for Claude should only be runnable when:

- a valid local Claude CLI session exists
- a ready Claude worker exists

### Codex auth path

Codex becomes a real `oauth_token` provider credential with PKCE.

The backend owns:

- OAuth initiate
- pending state tracking
- localhost callback completion
- token exchange
- refresh via refresh token

This remains local-only for v1. The redirect URI is expected to point at the local API server.

The persisted credential should store:

- `provider = "codex"`
- `credential_type = "oauth_token"`
- encrypted access token
- encrypted refresh token
- token expiry
- scopes
- optional account metadata if returned by the provider

Provider readiness for Codex should only be runnable when:

- a valid active OAuth token exists
- a ready Codex worker exists

## Backend Changes

### Settings

Add explicit settings for Codex OAuth, likely on the main settings object:

- `codex_oauth_client_id`
- `codex_oauth_authorize_url`
- `codex_oauth_token_url`
- `codex_oauth_redirect_uri`
- `codex_oauth_scopes`

Add Claude CLI discovery settings only if needed, likely:

- `claude_cli_command`
- `claude_cli_config_dir`

Defaults should be local-development friendly.

### Auth application layer

Add a concrete Codex OAuth client implementing the existing `OAuthProviderClient` protocol and register it in `_OAUTH_CLIENTS`.

Add a Claude CLI discovery/validation service responsible for:

- locating Claude CLI config/session state
- invoking `claude auth status` when possible
- normalizing the discovered session into a stored credential request

Keep credential persistence in the existing `auth_credentials` table.

### API surface

Keep:

- `POST /auth/credentials/oauth/initiate`
- `GET /auth/credentials/oauth/callback`
- `POST /auth/credentials/{credential_id}/refresh`

Those become genuinely usable for `provider = "codex"`.

Add a Claude-specific connect endpoint, for example:

- `POST /auth/credentials/claude-cli/connect`

This endpoint should:

- discover local Claude CLI auth
- validate it
- create or update a `local_cli_session` credential
- return the resulting credential

Refresh remains OAuth-only and should reject Claude CLI credentials.

### Provider readiness

Update readiness logic so the provider-specific messages become real:

- Claude missing auth: no valid local Claude CLI session detected
- Codex missing auth: no valid OAuth credential detected
- Claude stale auth: detected session is invalid or expired
- Codex stale auth: access token expired and refresh failed, or refresh token invalid

## Frontend Changes

### Auth management UI

Make provider actions explicit:

- Claude: `Reuse Claude CLI session`
- Codex: `OAuth redirect`

Claude should no longer present as a normal OAuth provider in the add-credential flow.

Codex should keep the redirect-driven flow and surface provider configuration errors clearly if local env settings are missing.

### Bootstrap and readiness UI

Bootstrap and worker/provider panels should distinguish:

- missing Claude CLI auth
- invalid Claude CLI session
- missing Codex OAuth
- expired Codex OAuth

The UI should tell the operator what to do next instead of showing a generic missing-auth state.

## Data Flow

### Claude

1. Operator clicks `Reuse Claude CLI session`
2. Frontend calls Claude connect endpoint
3. Backend validates local Claude auth
4. Backend creates or updates `local_cli_session` credential
5. Provider readiness recomputes
6. Bootstrap and worker UI show Claude as runnable once a worker exists

### Codex

1. Operator clicks `OAuth redirect`
2. Frontend calls OAuth initiate for `codex`
3. Backend creates PKCE state and returns auth URL
4. Browser completes provider sign-in
5. Local callback hits Helaicopter backend
6. Backend exchanges code for token bundle and stores credential
7. Provider readiness recomputes
8. Bootstrap and worker UI show Codex as runnable once a worker exists

## Error Handling

### Claude errors

- Claude CLI binary missing
- Claude CLI not signed in
- Claude config/session files unreadable
- discovered session metadata incomplete

These should surface as user-actionable `400`-class API errors where appropriate, not generic fetch failures.

### Codex errors

- OAuth client not configured
- state missing or expired
- token exchange rejected
- refresh rejected

These should remain explicit backend errors with readable frontend messages.

## Testing

### Backend unit tests

- Codex OAuth client URL generation
- Codex callback exchange persistence
- Codex refresh behavior
- Claude CLI discovery success
- Claude CLI discovery failure modes
- provider readiness for both real auth paths

### API tests

- Claude connect endpoint creates a `local_cli_session` credential
- Claude connect endpoint returns actionable errors when CLI auth is unavailable
- Codex initiate works when configured
- Codex callback persists token-backed credentials
- Codex refresh updates stored credentials

### Frontend tests

- auth management renders Claude connect action and Codex OAuth action
- bootstrap/readiness copy distinguishes provider-specific blocked states

### Manual verification

- local Claude CLI already authenticated: connect succeeds and readiness flips to runnable when a Claude worker exists
- local Codex OAuth configured: redirect/callback stores credential and readiness flips to runnable when a Codex worker exists

## File Areas Expected To Change

- `python/helaicopter_api/application/auth.py`
- `python/helaicopter_api/router/auth.py`
- `python/helaicopter_api/schema/auth.py`
- `python/helaicopter_api/application/provider_readiness.py`
- `python/helaicopter_api/server/settings.py`
- `src/components/auth/auth-management-section.tsx`
- `src/components/auth/add-credential-dialog.tsx`
- `src/lib/client/auth.ts`
- tests covering auth, readiness, and UI flows

## Risks

- Claude CLI auth state may vary across local environments, so validation needs a small fallback ladder rather than a single brittle probe
- Codex OAuth needs correct provider endpoints and client configuration; without that, the UX regresses into configuration errors again
- the current encryption helper uses an in-memory generated Fernet key, which means restarted processes cannot decrypt earlier stored secrets; that is acceptable for local development only and may need follow-up if this auth store becomes durable across sessions

## Recommended Next Step

Write and execute an implementation plan with this sequence:

1. Codex OAuth settings and concrete client
2. Claude CLI connect/discovery flow
3. provider-readiness updates
4. auth management UI changes
5. local manual verification with Playwright and targeted tests
