# Phase 1: Responsive Viewports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Helaicopter web app fully responsive across three viewports — mobile (< 640px), iPad (768px+), and laptop (1024px+) — with a hamburger-driven sidebar drawer on mobile/iPad.

**Architecture:** Add a SidebarProvider context, MobileHeader component, and SidebarDrawer overlay. The existing AppSidebar component is reused in both desktop (static) and mobile (drawer) contexts. Page content adapts via Tailwind responsive utilities.

**Tech Stack:** Next.js 16 (App Router), React 19, Tailwind CSS v4, Radix UI Dialog (for drawer)

**Spec:** `docs/superpowers/specs/2026-03-24-mobile-interface-masterplan-design.md` (Phase 1 section)

**Prerequisite:** Phase 0 must be complete.

---

## File Structure

### Files to CREATE:
- `src/components/layout/sidebar-provider.tsx` — React context for sidebar open/close state
- `src/components/layout/mobile-header.tsx` — Sticky top bar with hamburger icon, visible < lg
- `src/components/layout/sidebar-drawer.tsx` — Slide-over overlay wrapping AppSidebar for mobile/iPad

### Files to MODIFY:
- `src/app/layout.tsx` — Restructure to use SidebarProvider, conditional desktop/mobile rendering
- `src/components/layout/app-sidebar.tsx` — Accept `onNavClick` prop to close drawer on navigation
- `src/app/globals.css` — Add safe-area-inset CSS custom properties for iOS

---

## Task 1: Add viewport metadata to root layout

**Files:**
- Modify: `src/app/layout.tsx`

- [ ] **Step 1: Read the current layout file**

Read `src/app/layout.tsx` to confirm the current Metadata export and structure.

- [ ] **Step 2: Add viewport export**

Next.js 16 uses a separate `viewport` export. Add it alongside the existing `metadata` export in `src/app/layout.tsx`:

```typescript
import type { Viewport } from "next";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};
```

The `viewportFit: "cover"` enables `env(safe-area-inset-*)` CSS variables for iOS notch handling.

- [ ] **Step 3: Verify the build**

Run: `cd /Users/tony/Code/helaicopter-main && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/app/layout.tsx
git commit -m "feat: add viewport metadata with device-width and viewport-fit cover"
```

---

## Task 2: Create SidebarProvider context

**Files:**
- Create: `src/components/layout/sidebar-provider.tsx`

- [ ] **Step 1: Create the provider file**

Create `src/components/layout/sidebar-provider.tsx`:

```typescript
"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

interface SidebarContextValue {
  open: boolean;
  toggle: () => void;
  close: () => void;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const toggle = useCallback(() => setOpen((prev) => !prev), []);
  const close = useCallback(() => setOpen(false), []);

  return (
    <SidebarContext.Provider value={{ open, toggle, close }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar(): SidebarContextValue {
  const ctx = useContext(SidebarContext);
  if (!ctx) throw new Error("useSidebar must be used within SidebarProvider");
  return ctx;
}
```

- [ ] **Step 2: Verify no type errors**

Run: `cd /Users/tony/Code/helaicopter-main && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/components/layout/sidebar-provider.tsx
git commit -m "feat: add SidebarProvider context for mobile sidebar state"
```

---

## Task 3: Create MobileHeader component

**Files:**
- Create: `src/components/layout/mobile-header.tsx`

- [ ] **Step 1: Create the mobile header file**

Create `src/components/layout/mobile-header.tsx`:

```typescript
"use client";

import { Menu } from "lucide-react";
import { useSidebar } from "./sidebar-provider";

export function MobileHeader({ className }: { className?: string }) {
  const { toggle } = useSidebar();

  return (
    <header
      className={`sticky top-0 z-40 flex items-center gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/60 ${className ?? ""}`}
      style={{ paddingTop: `max(0.75rem, env(safe-area-inset-top))` }}
    >
      <button
        type="button"
        onClick={toggle}
        className="inline-flex h-10 w-10 items-center justify-center rounded-md hover:bg-accent"
        aria-label="Toggle navigation menu"
      >
        <Menu className="h-5 w-5" />
      </button>
      <span className="text-sm font-semibold">Helaicopter</span>
    </header>
  );
}
```

The 44px (h-10 w-10) button meets the minimum iOS tap target size. `env(safe-area-inset-top)` handles the iPhone notch.

- [ ] **Step 2: Verify no type errors**

Run: `cd /Users/tony/Code/helaicopter-main && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/components/layout/mobile-header.tsx
git commit -m "feat: add MobileHeader with hamburger toggle"
```

---

## Task 4: Create SidebarDrawer component

**Files:**
- Create: `src/components/layout/sidebar-drawer.tsx`
- Modify: `src/components/layout/app-sidebar.tsx`

- [ ] **Step 1: Read the current app-sidebar.tsx**

Read `src/components/layout/app-sidebar.tsx` to understand the nav link click behavior.

- [ ] **Step 2: Add onNavClick prop to AppSidebar**

Modify `src/components/layout/app-sidebar.tsx` to accept an optional `onNavClick` callback. Wire it into every navigation link's `onClick`:

```typescript
// Add to the component props:
export function AppSidebar({ onNavClick }: { onNavClick?: () => void } = {}) {
```

On each `<Link>` element in the nav, add `onClick={onNavClick}`.

This allows the drawer to close the sidebar when a nav item is clicked, without changing the desktop sidebar behavior (where `onNavClick` is undefined/no-op).

- [ ] **Step 3: Create the drawer file**

Create `src/components/layout/sidebar-drawer.tsx`:

```typescript
"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { useSidebar } from "./sidebar-provider";
import { AppSidebar } from "./app-sidebar";

export function SidebarDrawer() {
  const { open, close } = useSidebar();
  const pathname = usePathname();

  // Close drawer on route change
  useEffect(() => {
    close();
  }, [pathname, close]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={close}
        aria-hidden="true"
      />
      {/* Drawer panel */}
      <div className="fixed inset-y-0 left-0 w-64 animate-in slide-in-from-left duration-200">
        <div className="relative h-full">
          <button
            type="button"
            onClick={close}
            className="absolute right-2 top-2 z-10 inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-accent"
            aria-label="Close navigation menu"
          >
            <X className="h-4 w-4" />
          </button>
          <AppSidebar onNavClick={close} />
        </div>
      </div>
    </div>
  );
}
```

Note: Tailwind CSS v4 includes `animate-in` and `slide-in-from-left` utilities via the built-in animation plugin. If these aren't available, use a simple CSS transition or `@keyframes` in globals.css.

- [ ] **Step 4: Verify no type errors**

Run: `cd /Users/tony/Code/helaicopter-main && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add src/components/layout/sidebar-drawer.tsx src/components/layout/app-sidebar.tsx
git commit -m "feat: add SidebarDrawer overlay and wire onNavClick to AppSidebar"
```

---

## Task 5: Restructure root layout

**Files:**
- Modify: `src/app/layout.tsx`

- [ ] **Step 1: Read the current layout**

Read `src/app/layout.tsx` to see the current structure.

- [ ] **Step 2: Update the layout**

Replace the inner layout structure. The current structure is:
```tsx
<div className="flex min-h-screen">
  <AppSidebar />
  <main className="flex-1 p-8 overflow-auto">{children}</main>
</div>
```

Change to:
```tsx
import { SidebarProvider } from "@/components/layout/sidebar-provider";
import { MobileHeader } from "@/components/layout/mobile-header";
import { SidebarDrawer } from "@/components/layout/sidebar-drawer";

// ... inside the body:
<SidebarProvider>
  <div className="flex min-h-screen">
    {/* Desktop sidebar — hidden on mobile/iPad */}
    <div className="hidden lg:block">
      <AppSidebar />
    </div>

    {/* Mobile/iPad drawer overlay */}
    <SidebarDrawer />

    <div className="flex-1 flex flex-col min-w-0">
      {/* Mobile/iPad header with hamburger */}
      <MobileHeader className="lg:hidden" />

      <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto">
        {children}
      </main>
    </div>
  </div>
</SidebarProvider>
```

Key changes:
- Desktop sidebar wrapped in `hidden lg:block`
- SidebarDrawer renders the overlay (only when open, only < lg)
- MobileHeader with `lg:hidden` shows hamburger on mobile/iPad
- Main padding reduced on small screens: `p-4 sm:p-6 lg:p-8`
- `min-w-0` on the flex child prevents flex overflow issues

- [ ] **Step 3: Verify the build**

Run: `cd /Users/tony/Code/helaicopter-main && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Manual test**

Run: `cd /Users/tony/Code/helaicopter-main && npm run dev:web`
Open http://localhost:3000 in browser.
- At full width: sidebar visible on left, no hamburger
- Resize to < 1024px: sidebar disappears, hamburger appears in top bar
- Click hamburger: sidebar slides in as overlay
- Click a nav item: drawer closes, page navigates
- Click backdrop: drawer closes

- [ ] **Step 5: Commit**

```bash
git add src/app/layout.tsx
git commit -m "feat: restructure root layout with responsive sidebar (desktop static, mobile drawer)"
```

---

## Task 6: Add safe-area CSS and iOS WebView support

**Files:**
- Modify: `src/app/globals.css`

- [ ] **Step 1: Read globals.css**

Read `src/app/globals.css` to find the right place to add iOS-specific styles.

- [ ] **Step 2: Add safe-area and iOS styles**

Add the following at the end of `src/app/globals.css` (before any closing comments):

```css
/* iOS safe area and WebView support */
@supports (padding-top: env(safe-area-inset-top)) {
  .safe-area-top {
    padding-top: env(safe-area-inset-top);
  }
  .safe-area-bottom {
    padding-bottom: env(safe-area-inset-bottom);
  }
}

/* Prevent rubber-banding on non-scrollable areas (iOS WebView) */
html {
  overscroll-behavior: none;
}
```

- [ ] **Step 3: Commit**

```bash
git add src/app/globals.css
git commit -m "feat: add safe-area CSS utilities and iOS overscroll behavior"
```

---

## Task 7: Make analytics page responsive

**Files:**
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Read the analytics page**

Read `src/app/page.tsx` to understand the current grid and layout patterns.

- [ ] **Step 2: Audit and fix responsive grids**

Review each grid/flex layout in the analytics page and ensure it works on all three viewports:

- Stats cards grid: should use `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6`
- Rate cards: `grid-cols-1 xl:grid-cols-3` (already fine — stacks on mobile)
- Charts: `grid-cols-1 lg:grid-cols-2` (already fine — stacks on mobile)
- Filter controls in PageHeader actions: wrap on mobile via `flex flex-wrap gap-2`
- Date picker / provider filter: ensure they don't overflow on small screens

Fix any hardcoded widths or layouts that would break below 640px. Most grids already start with `grid-cols-1` so they should stack naturally.

- [ ] **Step 3: Verify visually**

Run dev server and check analytics page at mobile (390px), iPad (820px), and laptop (1440px) widths using browser dev tools.

- [ ] **Step 4: Commit**

```bash
git add src/app/page.tsx
git commit -m "feat: ensure analytics page responsive grids work across all viewports"
```

---

## Task 8: Make conversations page responsive

**Files:**
- Modify: `src/components/conversation/conversation-list.tsx`
- Modify: `src/components/conversation/conversation-viewer.tsx`

- [ ] **Step 1: Read conversation-list.tsx**

Read the full file to understand the filter bar and card grid layout.

- [ ] **Step 2: Fix conversation list responsive layout**

Ensure:
- Filter bar: controls stack vertically on mobile (`flex flex-col sm:flex-row gap-2`)
- Search input: full width on mobile
- Card grid: `grid-cols-1 md:grid-cols-2 xl:grid-cols-3`
- Cards: adequate padding and tap targets on mobile

- [ ] **Step 3: Read and fix conversation-viewer.tsx**

Ensure:
- Tab bar doesn't overflow on small screens (use `overflow-x-auto` if needed)
- Message content: prose width adapts to screen
- Tool call blocks: horizontal scroll if content overflows
- Metadata sidebar (if any): stacks below content on mobile

- [ ] **Step 4: Verify visually**

Check conversations page at all three viewport widths.

- [ ] **Step 5: Commit**

```bash
git add src/components/conversation/conversation-list.tsx src/components/conversation/conversation-viewer.tsx
git commit -m "feat: make conversations page responsive across mobile/ipad/laptop"
```

---

## Task 9: Make remaining pages responsive

**Files:**
- Modify: `src/app/orchestration/page.tsx` (if needed)
- Modify: `src/app/plans/page.tsx` (if needed)
- Modify: `src/app/databases/page.tsx` (if needed)
- Modify: `src/app/pricing/page.tsx` (if needed)
- Modify: `src/app/docs/page.tsx` (if needed)
- Modify: `src/app/schema/page.tsx` (if needed)

- [ ] **Step 1: Audit each remaining page**

For each page, open at 390px width in dev tools and identify any layout issues:
- Content overflowing viewport
- Horizontal scroll on entire page
- Elements too small to tap
- Fixed widths that don't adapt

- [ ] **Step 2: Fix issues found**

Common fixes:
- Tables: wrap in `<div className="overflow-x-auto">` for horizontal scroll
- Hardcoded widths: replace with responsive equivalents
- Side-by-side layouts: stack on mobile with `flex-col lg:flex-row`
- Padding: use `p-4 sm:p-6 lg:p-8` pattern

- [ ] **Step 3: Verify visually**

Check each page at all three viewport widths.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: make all remaining pages responsive across viewports"
```

---

## Task 10: Final responsive verification

- [ ] **Step 1: Full build check**

Run: `cd /Users/tony/Code/helaicopter-main && npm run build`
Expected: Build succeeds

Run: `cd /Users/tony/Code/helaicopter-main && npm run lint`
Expected: No lint errors

- [ ] **Step 2: Cross-viewport visual audit**

Run dev server and systematically check every page at three widths:
- 390px (iPhone)
- 820px (iPad)
- 1440px (MacBook)

Verify:
- Sidebar hidden on mobile/iPad, hamburger visible
- Sidebar visible on laptop, no hamburger
- Drawer opens/closes correctly
- All content readable and tappable at each width
- No horizontal overflow on any page
- Charts and grids adapt appropriately

- [ ] **Step 3: Commit any final fixes**

```bash
git add -A
git commit -m "fix: responsive viewport polish and edge cases"
```
