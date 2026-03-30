# Homebrew Installation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a working Homebrew installation path that installs a `helaicopter` command, bootstraps the app into a user-writable runtime directory, and documents how the Brew flow works.

**Architecture:** Ship a HEAD-only Homebrew formula plus a standalone launcher script. The formula stages repo contents into `libexec`, while the launcher handles runtime bootstrap, frontend build, and coordinated backend/frontend startup from a user-owned directory.

**Tech Stack:** Homebrew formula DSL (Ruby), Python stdlib launcher, npm, uv, Next.js, FastAPI, pytest

---

### Task 1: Add failing tests for the Homebrew launcher contract

**Files:**
- Create: `tests/test_homebrew_launcher.py`

- [ ] **Step 1: Write the failing test**

```python
def test_sync_runtime_tree_copies_staged_source_without_mutable_artifacts():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_homebrew_launcher.py`
Expected: FAIL because the launcher module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def sync_staged_source(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_homebrew_launcher.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_homebrew_launcher.py packaging/homebrew/launcher.py
git commit -m "test: cover homebrew launcher bootstrap"
```

### Task 2: Implement the launcher and formula assets

**Files:**
- Create: `packaging/homebrew/launcher.py`
- Create: `Formula/helaicopter.rb`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Add the missing runtime dependency**

```toml
dependencies = [
  ...
  "cryptography>=...",
]
```

- [ ] **Step 2: Implement the launcher CLI**

```python
def main() -> int:
    ...
```

- [ ] **Step 3: Add the Homebrew formula**

```ruby
class Helaicopter < Formula
  ...
end
```

- [ ] **Step 4: Run packaging-focused verification**

Run: `uv run pytest -q tests/test_homebrew_launcher.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock packaging/homebrew/launcher.py Formula/helaicopter.rb
git commit -m "feat: add homebrew launcher and formula"
```

### Task 3: Document the Homebrew install flow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README Homebrew install and maintenance sections**

```md
## Install with Homebrew
...
```

- [ ] **Step 2: Verify the README commands match the new assets**

Run: `ruby -c Formula/helaicopter.rb`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: explain homebrew installation"
```

### Task 4: Verify the branch for review

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `Formula/helaicopter.rb`
- Create: `packaging/homebrew/launcher.py`
- Create: `tests/test_homebrew_launcher.py`
- Create: `docs/superpowers/specs/2026-03-30-homebrew-installation-design.md`
- Create: `docs/superpowers/plans/2026-03-30-homebrew-installation.md`

- [ ] **Step 1: Run focused verification**

Run: `uv run pytest -q tests/test_homebrew_launcher.py tests/test_api_smoke.py`
Expected: PASS

- [ ] **Step 2: Run syntax validation for the formula**

Run: `ruby -c Formula/helaicopter.rb`
Expected: `Syntax OK`

- [ ] **Step 3: Review git diff**

Run: `git diff --stat`
Expected: Only the Homebrew packaging, runtime dependency, docs, and tests planned above.

- [ ] **Step 4: Commit**

```bash
git add Formula/helaicopter.rb packaging/homebrew/launcher.py tests/test_homebrew_launcher.py README.md pyproject.toml uv.lock docs/superpowers/specs/2026-03-30-homebrew-installation-design.md docs/superpowers/plans/2026-03-30-homebrew-installation.md
git commit -m "feat: add homebrew installation support"
```
