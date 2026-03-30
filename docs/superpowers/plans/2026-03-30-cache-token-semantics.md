# Cache Token Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Claude cache token overcounting from fragmented assistant events and align Codex total-token presentation with Codex-native semantics.

**Architecture:** Keep provider-specific parsing rules in the conversation application layer, where raw Claude and Codex artifacts are already normalized into shared response models. Lock the behavior with focused API and analytics regression tests so the UI and warehouse-backed summaries stay consistent.

**Tech Stack:** Python, FastAPI, pytest, TypeScript/React

---

### Task 1: Add Claude Fragment Regression Coverage

**Files:**
- Modify: `tests/test_api_conversations.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run it to verify it fails**
- [ ] **Step 3: Implement minimal summary/detail aggregation fix**
- [ ] **Step 4: Run the targeted conversation tests to verify they pass**

### Task 2: Add Codex Total-Token Semantics Coverage

**Files:**
- Modify: `tests/test_api_conversations.py`
- Modify: `tests/test_api_analytics.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run them to verify they fail**
- [ ] **Step 3: Implement Codex-native total-token semantics**
- [ ] **Step 4: Run the targeted analytics and conversation tests to verify they pass**

### Task 3: Verify And Ship

**Files:**
- Modify: `python/helaicopter_api/application/conversations.py`
- Modify: `python/helaicopter_api/pure/analytics.py`
- Modify: `src/components/conversation/conversation-list.tsx`
- Modify: `python/helaicopter_api/pure/conversation_dag.py`

- [ ] **Step 1: Run the focused test suite**
- [ ] **Step 2: Run any needed frontend/unit checks**
- [ ] **Step 3: Review diff for accidental scope creep**
- [ ] **Step 4: Commit and open PR**
