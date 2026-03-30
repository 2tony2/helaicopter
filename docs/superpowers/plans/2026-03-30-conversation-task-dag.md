# Conversation Task DAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the conversation Tasks JSON dump with a DAG-based task view, including a Codex fallback that turns `update_plan` steps into graph nodes.

**Architecture:** Add a pure frontend task-graph builder that accepts raw conversation task payloads plus optional Codex plans, normalize them into nodes and edges, and render them in a dedicated task DAG component. Keep the graph rendering isolated from the conversation viewer so parsing logic remains testable and the UI stays easy to evolve.

**Tech Stack:** Next.js, React, TypeScript, React Flow, dagre, Node test runner via `tsx --test`

---

### Task 1: Define the task DAG model in tests

**Files:**
- Create: `src/lib/conversation-task-dag.test.ts`
- Modify: `src/lib/types.ts`
- Test: `src/lib/conversation-task-dag.test.ts`

- [ ] **Step 1: Write the failing test**

Add tests that prove:
- explicit `dependsOn` fields become graph edges
- ordered task arrays without dependencies become a linear chain
- Codex plan steps become synthetic ordered task nodes

- [ ] **Step 2: Run test to verify it fails**

Run: `npx tsx --test src/lib/conversation-task-dag.test.ts`
Expected: FAIL because the task DAG builder does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create a pure builder that normalizes raw task payloads and emits graph nodes, edges, and summary stats.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx tsx --test src/lib/conversation-task-dag.test.ts`
Expected: PASS

### Task 2: Render the graph in the conversation Tasks tab

**Files:**
- Create: `src/components/conversation/conversation-task-dag-view.tsx`
- Modify: `src/components/conversation/conversation-viewer.tsx`
- Test: `src/app/conversations/[...segments]/page.test.ts`

- [ ] **Step 1: Write the failing test**

Extend the conversation page/viewer test coverage so a Codex conversation with plans but no `/tasks` payload renders task graph content in the Tasks tab.

- [ ] **Step 2: Run test to verify it fails**

Run: `npx tsx --test src/app/conversations/[...segments]/page.test.ts`
Expected: FAIL because the Tasks tab still only renders raw JSON / empty state.

- [ ] **Step 3: Write minimal implementation**

Add a task DAG view component, connect it to the Tasks tab, and keep a raw payload section beneath it for debugging.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx tsx --test src/app/conversations/[...segments]/page.test.ts`
Expected: PASS

### Task 3: Verify and finish

**Files:**
- Modify: `docs/superpowers/specs/2026-03-30-conversation-task-dag-design.md`
- Modify: `docs/superpowers/plans/2026-03-30-conversation-task-dag.md`
- Test: `src/lib/conversation-task-dag.test.ts`
- Test: `src/app/conversations/[...segments]/page.test.ts`
- Test: `npm run lint -- src/components/conversation/conversation-viewer.tsx src/components/conversation/conversation-task-dag-view.tsx src/lib/conversation-task-dag.ts src/lib/types.ts`

- [ ] **Step 1: Run focused verification**

Run:
- `npx tsx --test src/lib/conversation-task-dag.test.ts`
- `npx tsx --test src/app/conversations/[...segments]/page.test.ts`

Expected: PASS

- [ ] **Step 2: Run lint on touched frontend files**

Run: `npx eslint src/components/conversation/conversation-viewer.tsx src/components/conversation/conversation-task-dag-view.tsx src/lib/conversation-task-dag.ts src/lib/types.ts`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-03-30-conversation-task-dag-design.md \
  docs/superpowers/plans/2026-03-30-conversation-task-dag.md \
  src/lib/conversation-task-dag.ts src/lib/conversation-task-dag.test.ts \
  src/components/conversation/conversation-task-dag-view.tsx \
  src/components/conversation/conversation-viewer.tsx \
  src/lib/types.ts src/app/conversations/[...segments]/page.test.ts
git commit -m "feat: render conversation tasks as a dag"
```
