export const CLAUDE_EVALUATION_MODELS = [
  "claude-opus-4-6",
  "claude-sonnet-4-6",
  "claude-opus-4",
  "claude-sonnet-4",
  "claude-haiku-4-5-20251001",
  "claude-haiku-3-5",
];

export const CODEX_EVALUATION_MODELS = [
  "gpt-5",
  "o3",
  "o4-mini",
  "gpt-5.1",
  "gpt-5.2",
  "gpt-5.4",
];

export type EvaluationProvider = "claude" | "codex";
export type EvaluationScope = "full" | "failed_tool_calls" | "guided_subset";
