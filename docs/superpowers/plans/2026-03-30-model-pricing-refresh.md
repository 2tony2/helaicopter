# Model Pricing Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update Codex/OpenAI and Claude pricing to current official values, add current GPT-5.4 family coverage, and remove stale Claude 4.6 long-context premium assumptions.

**Architecture:** Keep `python/helaicopter_semantics/pricing.py` as the canonical source, mirror the changes into the deprecated compat helper and frontend constants, then align fuzzy matching, long-context logic, and pricing-page copy with those tables. Preserve legacy model IDs for historical analytics while making latest-family resolution prefer current versions.

**Tech Stack:** Python 3.13, pytest, TypeScript, Node test runner with `tsx`, Next.js

---

### Task 1: Lock the expected behavior with failing tests

**Files:**
- Modify: `tests/test_semantics.py`
- Modify: `tests/test_pricing_compat.py`
- Modify: `src/lib/pricing.test.ts`

- [ ] **Step 1: Write failing Python tests for current pricing aliases and 4.6 long-context behavior**

Add assertions that:

- `resolve_pricing("gpt-5.4-mini")` resolves to a new GPT-5.4 mini entry
- `resolve_pricing("gpt-5.4-nano")` resolves to a new GPT-5.4 nano entry
- generic `sonnet` resolves to `claude-sonnet-4-6`
- `supports_long_context_premium("claude-opus-4-6")` is false
- `supports_long_context_premium("claude-sonnet-4-6")` is false
- `supports_long_context_premium("claude-sonnet-4-5-20250929")` remains true for legacy compatibility

- [ ] **Step 2: Run Python tests to verify they fail**

Run: `uv run pytest tests/test_semantics.py tests/test_pricing_compat.py -q`
Expected: FAIL on the new pricing alias and long-context assertions.

- [ ] **Step 3: Write failing frontend tests for latest model matching and 4.6 cost behavior**

Add assertions that:

- `getPricing("gpt-5.4-mini")` and `getPricing("gpt-5.4-nano")` resolve to new OpenAI pricing entries
- `getPricing("some-sonnet")` resolves to `claude-sonnet-4-6`
- `calculateCostWithLongContext(..., "claude-sonnet-4-6")` matches base cost
- `calculateCostWithLongContext(..., "claude-sonnet-4-5-20250929")` still applies premium

- [ ] **Step 4: Run the frontend pricing test to verify it fails**

Run: `node --import tsx --test src/lib/pricing.test.ts`
Expected: FAIL on the new resolution and long-context assertions.

### Task 2: Update canonical and mirrored pricing tables

**Files:**
- Modify: `python/helaicopter_semantics/pricing.py`
- Modify: `python/helaicopter_api/pure/pricing.py`
- Modify: `src/lib/constants.ts`

- [ ] **Step 1: Add the latest GPT-5.4 family pricing entries**

Add `gpt-5.4-mini` and `gpt-5.4-nano` using the current API rates:

- `gpt-5.4-mini`: input `0.75`, output `4.5`, cached input `0.075`
- `gpt-5.4-nano`: input `0.20`, output `1.25`, cached input `0.02`

- [ ] **Step 2: Preserve legacy entries while updating latest-family comments**

Keep existing legacy OpenAI/Codex entries in place so historical pricing remains stable.

- [ ] **Step 3: Update fuzzy matching to prefer latest tracked Sonnet and GPT-5.4 family aliases**

Match:

- `gpt-5.4-mini` and `gpt5.4-mini`
- `gpt-5.4-nano` and `gpt5.4-nano`
- generic `sonnet` to `claude-sonnet-4-6`

- [ ] **Step 4: Run Python and frontend pricing tests**

Run:

- `uv run pytest tests/test_semantics.py tests/test_pricing_compat.py -q`
- `node --import tsx --test src/lib/pricing.test.ts`

Expected: PASS for updated resolution tests, with long-context assertions still pending until Task 3 if needed.

### Task 3: Remove stale Claude 4.6 long-context premium behavior and refresh docs/UI

**Files:**
- Modify: `python/helaicopter_semantics/pricing.py`
- Modify: `python/helaicopter_api/pure/pricing.py`
- Modify: `src/lib/pricing.ts`
- Modify: `src/app/pricing/page.tsx`
- Modify: `python/helaicopter_semantics/README.md`

- [ ] **Step 1: Change premium detection to exclude Claude 4.6 models**

Keep long-context premium support only for legacy models that still require it. Remove Opus 4.6 and Sonnet 4.6 from premium detection.

- [ ] **Step 2: Update frontend premium calculation to match**

Ensure `calculateCostWithLongContext()` does not apply a multiplier to Opus 4.6 or Sonnet 4.6.

- [ ] **Step 3: Rewrite pricing-page copy**

Replace the stale long-context premium table and caveats with current messaging:

- Opus 4.6 and Sonnet 4.6 use standard pricing across the full 1M window
- GPT-5.4 family pricing table includes mini and nano
- OpenAI/Codex cached input remains discounted rather than separate cache-write billing

- [ ] **Step 4: Update README language**

Change semantic-package documentation so it describes current long-context behavior accurately.

- [ ] **Step 5: Run the full targeted verification**

Run:

- `uv run pytest tests/test_semantics.py tests/test_pricing_compat.py -q`
- `node --import tsx --test src/lib/pricing.test.ts`

Expected: PASS

### Task 4: Final verification and branch completion

**Files:**
- Modify: `docs/superpowers/specs/2026-03-30-model-pricing-refresh-design.md`
- Modify: `docs/superpowers/plans/2026-03-30-model-pricing-refresh.md`
- Modify: implementation files from Tasks 1-3

- [ ] **Step 1: Review changed files for consistency**

Check that canonical Python pricing, compat Python pricing, frontend constants, matching logic, tests, README, and pricing-page copy all agree.

- [ ] **Step 2: Run final verification commands**

Run:

- `uv run pytest tests/test_semantics.py tests/test_pricing_compat.py -q`
- `node --import tsx --test src/lib/pricing.test.ts`

Expected: PASS

- [ ] **Step 3: Commit the work**

```bash
git add docs/superpowers/specs/2026-03-30-model-pricing-refresh-design.md \
  docs/superpowers/plans/2026-03-30-model-pricing-refresh.md \
  python/helaicopter_semantics/pricing.py \
  python/helaicopter_api/pure/pricing.py \
  python/helaicopter_semantics/README.md \
  src/lib/constants.ts \
  src/lib/pricing.ts \
  src/lib/pricing.test.ts \
  src/app/pricing/page.tsx \
  tests/test_semantics.py \
  tests/test_pricing_compat.py
git commit -m "feat: refresh codex and claude pricing"
```

- [ ] **Step 4: Push and create the PR**

Push the feature branch, then create a PR targeting `models` if that base exists; otherwise surface the missing-base decision before creating the PR.
