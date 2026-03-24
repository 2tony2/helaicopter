# Phase 2: Capacitor iPhone App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the responsive Helaicopter web app in a Capacitor native iOS shell for personal iPhone use, connecting to the Mac's FastAPI + Next.js server over Tailscale.

**Architecture:** Capacitor wraps the existing web app in a native WebView. The WebView points directly at the Next.js server running on the Mac over Tailscale (no static export). Native plugins add status bar theming, splash screen, haptics, and app lifecycle handling.

**Tech Stack:** Capacitor 6, Xcode, iOS, Tailscale, Next.js 16

**Spec:** `docs/superpowers/specs/2026-03-24-mobile-interface-masterplan-design.md` (Phase 2 section)

**Prerequisites:** Phase 0 (cleanup) and Phase 1 (responsive viewports) must be complete.

---

## File Structure

### Files to CREATE:
- `capacitor.config.ts` — Capacitor configuration (server URL, app ID, plugins)
- `ios/` — Generated Xcode project directory (via `npx cap add ios`)

### Files to MODIFY:
- `package.json` — Add Capacitor dependencies and scripts
- `src/app/layout.tsx` — Ensure viewport-fit=cover metadata present (done in Phase 1)
- `src/app/globals.css` — Safe area insets (done in Phase 1)
- `.gitignore` — Add iOS build artifacts

---

## Task 1: Install Capacitor dependencies

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Install Capacitor core and CLI**

Run:
```bash
cd /Users/tony/Code/helaicopter-main && npm install @capacitor/core @capacitor/cli
```

- [ ] **Step 2: Install native plugins**

Run:
```bash
cd /Users/tony/Code/helaicopter-main && npm install @capacitor/status-bar @capacitor/splash-screen @capacitor/haptics @capacitor/app
```

- [ ] **Step 3: Verify install**

Run: `npx cap --version`
Expected: Prints Capacitor version

- [ ] **Step 4: Commit**

```bash
git add package.json package-lock.json
git commit -m "feat: install capacitor core, cli, and native plugins"
```

---

## Task 2: Initialize Capacitor project

**Files:**
- Create: `capacitor.config.ts`
- Modify: `.gitignore`

- [ ] **Step 1: Create capacitor.config.ts**

Create `capacitor.config.ts` at the project root:

```typescript
import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.helaicopter.app",
  appName: "Helaicopter",
  server: {
    // Point at your Mac's Next.js server over Tailscale.
    // Replace with your actual Tailscale hostname.
    url: "http://YOUR_TAILSCALE_HOSTNAME:3000",
    cleartext: true, // Tailscale tunnel is already encrypted
  },
  ios: {
    contentInset: "automatic",
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: true,
      launchShowDuration: 1000,
      backgroundColor: "#ffffff",
    },
    StatusBar: {
      style: "DARK",
    },
  },
};

export default config;
```

Note: The `YOUR_TAILSCALE_HOSTNAME` placeholder must be replaced with the actual Tailscale machine name before building. You can find it with `tailscale status`.

- [ ] **Step 2: Add iOS platform**

Run:
```bash
cd /Users/tony/Code/helaicopter-main && npx cap add ios
```

Expected: Creates `ios/` directory with Xcode workspace.

- [ ] **Step 3: Update .gitignore**

Add to `.gitignore`:
```
# Capacitor iOS build artifacts
ios/App/Pods/
ios/App/App/public/
ios/App/DerivedData/
```

Keep the rest of `ios/` tracked so the Xcode project config is versioned.

- [ ] **Step 4: Commit**

```bash
git add capacitor.config.ts .gitignore ios/
git commit -m "feat: initialize capacitor ios project with tailscale server config"
```

---

## Task 3: Configure native iOS plugins

**Files:**
- Modify: `ios/App/App/AppDelegate.swift` (or create a Capacitor plugin bridge file)

- [ ] **Step 1: Read the generated AppDelegate**

Read `ios/App/App/AppDelegate.swift` to understand the Capacitor bootstrap.

- [ ] **Step 2: Add status bar and splash screen configuration**

Capacitor plugins are configured via `capacitor.config.ts` (already done in Task 2). The native side auto-registers plugins. Verify the plugins are recognized:

Run:
```bash
cd /Users/tony/Code/helaicopter-main && npx cap sync ios
```

Expected: Syncs plugins to native project without errors.

- [ ] **Step 3: Add app lifecycle handler**

Create or modify the web-side initialization to handle Capacitor App plugin events. Add a new file `src/lib/capacitor.ts`:

```typescript
import { Capacitor } from "@capacitor/core";
import { App } from "@capacitor/app";
import { StatusBar, Style } from "@capacitor/status-bar";

/**
 * Initialize Capacitor native features.
 * Call this once from the root layout's useEffect.
 * No-ops gracefully when running in a regular browser.
 */
export async function initCapacitor() {
  if (!Capacitor.isNativePlatform()) return;

  // Match status bar to app theme
  try {
    await StatusBar.setStyle({ style: Style.Dark });
  } catch {
    // StatusBar not available
  }

  // Refresh data when app returns to foreground
  App.addListener("appStateChange", ({ isActive }) => {
    if (isActive) {
      // SWR will automatically revalidate on window focus,
      // but we can also trigger a manual refresh here if needed.
      window.dispatchEvent(new Event("focus"));
    }
  });
}
```

- [ ] **Step 4: Wire initCapacitor into the app**

In `src/app/layout.tsx`, add a client component wrapper or useEffect that calls `initCapacitor()` on mount. Since layout.tsx may be a server component, create a small client wrapper:

```typescript
// src/components/layout/capacitor-init.tsx
"use client";

import { useEffect } from "react";
import { initCapacitor } from "@/lib/capacitor";

export function CapacitorInit() {
  useEffect(() => {
    initCapacitor();
  }, []);
  return null;
}
```

Add `<CapacitorInit />` inside the body of `src/app/layout.tsx`.

- [ ] **Step 5: Commit**

```bash
git add src/lib/capacitor.ts src/components/layout/capacitor-init.tsx src/app/layout.tsx
git commit -m "feat: add capacitor native plugin initialization (status bar, app lifecycle)"
```

---

## Task 4: Add npm scripts for Capacitor workflow

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Add Capacitor scripts**

Add these scripts to `package.json`:
```json
{
  "scripts": {
    "cap:sync": "cap sync ios",
    "cap:open": "cap open ios",
    "cap:run": "cap run ios"
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add package.json
git commit -m "feat: add capacitor npm scripts (sync, open, run)"
```

---

## Task 5: Build and test on iPhone

- [ ] **Step 1: Ensure Tailscale is running**

Verify Tailscale is connected on your Mac:
```bash
tailscale status
```
Note your machine's Tailscale hostname.

- [ ] **Step 2: Update capacitor.config.ts with real hostname**

Replace `YOUR_TAILSCALE_HOSTNAME` with your actual Tailscale hostname.

- [ ] **Step 3: Start the dev server**

Run: `cd /Users/tony/Code/helaicopter-main && npm run dev`

This starts both Next.js (port 3000) and FastAPI (port 30000).

- [ ] **Step 4: Sync and open in Xcode**

Run:
```bash
cd /Users/tony/Code/helaicopter-main && npx cap sync ios && npx cap open ios
```

This opens the Xcode workspace.

- [ ] **Step 5: Configure signing in Xcode**

In Xcode:
1. Select the "App" target
2. Go to Signing & Capabilities
3. Select your personal Apple ID team
4. Set a unique bundle identifier if needed

- [ ] **Step 6: Run on iPhone**

Connect your iPhone via USB (or use wireless debugging).
Select your iPhone as the run target in Xcode.
Press Run (Cmd+R).

Expected: App launches on iPhone, shows the Helaicopter web app loaded from your Mac over Tailscale.

- [ ] **Step 7: Verify native features**

Check:
- Status bar styled correctly
- Splash screen shows briefly on launch
- Safe area insets work (content not hidden behind notch)
- Navigation via hamburger menu works
- Scrolling is smooth
- Returning to app from background triggers data refresh

- [ ] **Step 8: Commit final config**

```bash
git add capacitor.config.ts
git commit -m "feat: configure capacitor with tailscale hostname for iphone deployment"
```

---

## Task 6: Optional haptic feedback

**Files:**
- Modify: `src/components/layout/app-sidebar.tsx`

- [ ] **Step 1: Add optional haptics to nav items**

In `src/components/layout/app-sidebar.tsx`, add a light haptic tap on nav clicks when running natively:

```typescript
import { Capacitor } from "@capacitor/core";
import { Haptics, ImpactStyle } from "@capacitor/haptics";

// In the nav click handler:
async function handleNavClick() {
  if (Capacitor.isNativePlatform()) {
    try {
      await Haptics.impact({ style: ImpactStyle.Light });
    } catch {
      // Haptics not available
    }
  }
  onNavClick?.();
}
```

Wire `handleNavClick` as the `onClick` on each nav `<Link>`.

- [ ] **Step 2: Test on device**

Verify light haptic feedback on nav taps when running on iPhone.

- [ ] **Step 3: Commit**

```bash
git add src/components/layout/app-sidebar.tsx
git commit -m "feat: add haptic feedback on nav taps for native ios"
```
