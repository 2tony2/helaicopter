# Local iPhone Developer Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Helaicopter runnable on a physical iPhone in local developer mode with a reliable mobile dev server path and clear setup instructions.

**Architecture:** Add a mobile-specific dev mode that exposes Next.js and FastAPI to the phone, route browser API calls through a Next.js backend proxy under `/api/backend/*`, and make the Capacitor iOS shell read its server URL from environment. Document the full workflow in README plus a dedicated guide.

**Tech Stack:** Next.js 16, FastAPI, Capacitor 8, Node.js, Xcode, Tailscale

---

## File Structure

- Modify: `scripts/dev-instance.mjs`
- Modify: `scripts/dev.mjs`
- Modify: `package.json`
- Modify: `capacitor.config.ts`
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/server/backend-api.ts`
- Modify: `src/lib/server/backend-api.test.ts`
- Create: `src/app/api/backend/[...path]/route.ts`
- Create: `src/lib/client/endpoints.test.ts`
- Modify: `README.md`
- Create: `docs/guides/iphone-dev-mode.md`

### Task 1: Add test coverage for proxy-aware URL behavior

**Files:**
- Create: `src/lib/client/endpoints.test.ts`
- Modify: `src/lib/server/backend-api.test.ts`

- [ ] **Step 1: Write a failing client endpoint test for proxy fallback**
- [ ] **Step 2: Run the targeted frontend test command and confirm it fails for the expected reason**
- [ ] **Step 3: Add a failing server helper test for proxy URL derivation if needed**
- [ ] **Step 4: Run the targeted server helper test command and confirm it fails**

### Task 2: Implement mobile-safe dev and proxy behavior

**Files:**
- Modify: `scripts/dev-instance.mjs`
- Modify: `scripts/dev.mjs`
- Modify: `package.json`
- Modify: `capacitor.config.ts`
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/server/backend-api.ts`
- Create: `src/app/api/backend/[...path]/route.ts`

- [ ] **Step 1: Teach the dev environment builder about mobile host binding and proxy mode**
- [ ] **Step 2: Update the dev scripts so Next.js and FastAPI can bind to `0.0.0.0`**
- [ ] **Step 3: Add package scripts for mobile dev and iOS sync/open/run**
- [ ] **Step 4: Update Capacitor config to consume environment-provided server URL**
- [ ] **Step 5: Add `/api/backend/*` proxy fallback support for browser clients**
- [ ] **Step 6: Implement the Next.js backend proxy route**
- [ ] **Step 7: Run targeted frontend tests and make them pass**

### Task 3: Write donkey-proof setup instructions

**Files:**
- Modify: `README.md`
- Create: `docs/guides/iphone-dev-mode.md`

- [ ] **Step 1: Add a short mobile section to the main README**
- [ ] **Step 2: Write a full iPhone guide with prerequisites, exact commands, Xcode steps, trust/developer mode steps, and troubleshooting**
- [ ] **Step 3: Make sure the instructions match the actual scripts and environment variables**

### Task 4: Verify and prepare PR output

**Files:**
- Test: `src/lib/client/endpoints.test.ts`
- Test: `src/lib/server/backend-api.test.ts`

- [ ] **Step 1: Run targeted frontend tests**
- [ ] **Step 2: Run targeted backend tests if touched**
- [ ] **Step 3: Run `npm run lint`**
- [ ] **Step 4: Run `npm run build`**
- [ ] **Step 5: Review the diff for correctness and write the PR summary**
