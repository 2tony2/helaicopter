# Local iPhone Developer Mode Design

**Date**: 2026-03-30
**Status**: Approved

## Goal

Make the existing Helaicopter Capacitor iOS shell actually usable on a real iPhone in local developer mode, with a setup that is simple enough for a non-iOS developer to follow.

## Problem

The repository already contains a Capacitor iOS project, native plugin wiring, and responsive layout work. The remaining blocker is the local runtime path:

- the default dev servers bind to `127.0.0.1`, so the iPhone cannot reach them over Tailscale or the local network
- the frontend bundle is configured to call FastAPI on `127.0.0.1`, which works on the Mac but breaks on the iPhone because `127.0.0.1` becomes the phone itself
- the repo does not yet provide a clear, copy-paste-friendly runbook for getting the app onto a physical iPhone in Developer Mode

## Approaches Considered

### 1. Recommended: exposed mobile dev mode plus same-origin backend proxy

Run Next.js and FastAPI on `0.0.0.0`, load the app in Capacitor from the Mac over Tailscale, and proxy browser-facing backend requests through a Next.js route such as `/api/backend/*`.

Why this is best:

- the iPhone only needs one app URL to load
- client-side code no longer needs to know the backend host or port
- browser requests stay same-origin from the phone's perspective
- the existing SSR helper can keep using direct backend access on the Mac
- the user workflow becomes predictable: start mobile dev servers, sync iOS shell, open Xcode, run on device

### 2. Direct dual-origin access from the phone

Expose both Next.js and FastAPI to the phone and configure the frontend bundle to call the FastAPI Tailscale URL directly.

Trade-offs:

- simpler code changes
- worse ergonomics because the user must manage both web and API URLs
- easier to misconfigure
- more likely to break when ports or hostnames change

### 3. Fully bundled offline-first native app

Ship static web assets inside the iOS app and move data access into native or embedded local storage paths.

Trade-offs:

- best eventual user experience
- much larger project
- does not match the current architecture, which depends on live repo-local files and FastAPI services on the Mac
- not appropriate for this iteration

## Chosen Design

Implement approach 1.

### Runtime model

1. A new mobile-oriented dev command starts both servers in a phone-reachable mode.
2. Next.js listens on `0.0.0.0` and serves the app to the iPhone over Tailscale.
3. FastAPI listens on `0.0.0.0` on its own port.
4. Browser-facing frontend requests use `/api/backend/*` when no explicit public API base URL is configured.
5. A Next.js route handler forwards those requests to FastAPI on the Mac.
6. Server-side Next.js fetches can continue using the existing backend helper and local port fallback.

### Configuration model

- `dev` keeps the current desktop-friendly behavior
- `dev:mobile` becomes the "I want to test on my phone" command
- `capacitor.config.ts` reads the mobile server URL from environment so users do not need to edit code for every hostname change
- dedicated iOS helper scripts guide syncing and opening the native project with the correct server URL

### User workflow

The happy path should become:

1. Start Tailscale on Mac and iPhone
2. Start repo mobile dev servers with one command
3. Export one environment variable with the Mac's Tailscale hostname
4. Sync and open the iOS project with one command
5. In Xcode, choose personal team signing and run to the connected iPhone
6. Enable Developer Mode and trust the app on device when prompted

## Files and Responsibilities

- `scripts/dev-instance.mjs`
  Decides checkout-local ports and dev environment variables. Needs a mobile/proxy-aware mode.
- `scripts/dev.mjs`
  Starts the child processes and should report the real host bindings being used.
- `package.json`
  Needs mobile-specific dev and iOS helper scripts.
- `capacitor.config.ts`
  Should derive the server URL from environment instead of a hardcoded placeholder-only path.
- `src/lib/client/endpoints.ts`
  Needs a same-origin proxy fallback that avoids colliding with page routes such as `/plans`.
- `src/app/api/backend/[...path]/route.ts`
  New proxy route handler that forwards browser requests to FastAPI.
- `README.md`
  Needs a clear "run on my iPhone" walkthrough.
- `docs/guides/iphone-dev-mode.md`
  New detailed, beginner-friendly runbook with exact commands, troubleshooting, and expected screens.

## Testing Strategy

- unit tests for client endpoint fallback behavior
- unit tests for backend URL resolution used by the proxy path
- route-handler-focused verification through build and manual mobile smoke checks
- final verification with:
  - targeted frontend tests
  - targeted backend tests
  - `npm run lint`
  - `npm run build`

## Risks and Mitigations

### Port confusion

Mitigation: keep using checkout-stable ports and print them clearly in the mobile dev command output.

### iPhone cannot reach the Mac

Mitigation: bind both servers to `0.0.0.0`, document Tailscale requirements, and give the user a direct URL to test in Safari before opening Xcode.

### Same-origin conflicts with existing Next.js pages

Mitigation: proxy through `/api/backend/*` instead of reusing top-level FastAPI paths such as `/plans`.

### Capacitor server URL drift

Mitigation: read the mobile URL from environment and provide wrapper scripts that inject it for sync/open steps.

## Success Criteria

- `npm run dev:mobile` starts a phone-reachable runtime without code edits
- the browser app can fetch backend data from a real iPhone without using `127.0.0.1`
- the Capacitor iOS shell syncs against an environment-provided server URL
- the repo contains beginner-friendly instructions for installing and running the app on a personal iPhone in Developer Mode
