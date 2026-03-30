# Homebrew Installation Design

## Goal

Add a Homebrew-based installation path for Helaicopter that works from a fresh macOS machine, documents the installation model clearly, and keeps the existing repository structure intact.

## Constraints

- The repository is a mixed Next.js and FastAPI application, not a single prebuilt binary.
- Runtime dependencies are split across Node.js and Python and currently rely on `npm` and `uv`.
- Homebrew formula builds run in a constrained environment, so relying on ad hoc dependency downloads during formula installation is fragile.
- The repository has no release tags today, so the initial Homebrew entry point needs to support an install-from-HEAD workflow.

## Recommended Approach

Use a custom, HEAD-only Homebrew formula in `Formula/helaicopter.rb` that installs the repository source into Homebrew’s `libexec` and exposes a `helaicopter` launcher command.

The launcher will:

1. Copy or refresh the staged source into a user-writable runtime directory.
2. Install Node production dependencies with `npm install --omit=dev`.
3. Install Python runtime dependencies with `uv sync --frozen`.
4. Build the frontend with `npm run build`.
5. Start the FastAPI backend and Next.js frontend together.

This keeps the formula itself simple and reproducible while moving mutable runtime state into the user’s home directory where `npm`, `uv`, logs, and build artifacts can live safely.

## Why Not A Homebrew Core-Style Formula

This repository is not distributed as a single npm package or Python wheel, and it includes both ecosystems in one runnable app. A Homebrew-core style formula would require vendoring a large cross-ecosystem dependency graph into the formula itself, which is unnecessary for this repository’s current distribution model.

The custom bootstrap formula is therefore the practical fit:

- Homebrew manages system-level prerequisites and the launcher command.
- The launcher manages repo-local app bootstrapping in a writable runtime directory.
- The README can explain the distinction so users know what Brew installs and what happens on first launch.

## Deliverables

- `Formula/helaicopter.rb` with Homebrew dependencies and a service entry.
- A standalone launcher/bootstrap script installed by the formula.
- Tests covering the launcher’s runtime-directory and staged-source behavior.
- README updates covering install, first-run behavior, and formula maintenance.
- A runtime dependency fix for `cryptography`, which is currently imported by the backend but not declared in the project dependencies.
