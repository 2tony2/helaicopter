import { join } from "path";
import { homedir } from "os";

export const WORKSPACES_DIR = join(homedir(), "Code");

export const CLAUDE_DIR = join(homedir(), ".claude");
export const PROJECTS_DIR = join(CLAUDE_DIR, "projects");
export const PLANS_DIR = join(CLAUDE_DIR, "plans");
export const TASKS_DIR = join(CLAUDE_DIR, "tasks");
export const HISTORY_FILE = join(CLAUDE_DIR, "history.jsonl");

export const CODEX_DIR = join(homedir(), ".codex");
export const CODEX_SESSIONS_DIR = join(CODEX_DIR, "sessions");
export const CODEX_HISTORY_FILE = join(CODEX_DIR, "history.jsonl");
export const CODEX_DB_PATH = join(CODEX_DIR, "state_5.sqlite");
