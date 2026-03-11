import Database from "better-sqlite3";
import { randomUUID } from "crypto";
import { execFileSync, spawn } from "child_process";
import { existsSync } from "fs";
import { homedir } from "os";
import { join } from "path";
import { getConversation } from "@/lib/claude-data";
import type {
  ConversationEvaluation,
  EvaluationPrompt,
  ProcessedConversation,
} from "@/lib/types";
import type {
  EvaluationProvider,
  EvaluationScope,
} from "@/lib/evaluation-models";

const OLTP_DB_PATH = join(
  process.cwd(),
  "public",
  "database-artifacts",
  "oltp",
  "helaicopter_oltp.sqlite"
);

export const DEFAULT_EVALUATION_PROMPT_NAME = "Default Conversation Review";
export const DEFAULT_EVALUATION_PROMPT = `Review this assistant conversation as an operator trying to improve future prompts, instructions, and conversation flow.

Focus on:
- unclear or under-specified user instructions
- avoidable tool failures and recovery quality
- places where the assistant should have clarified sooner
- bloated or distracting turns that increased cost without moving the task forward
- concrete rewrites that would make the next run cleaner

Return markdown with these sections:
## Executive Summary
## Instruction Problems
## Conversation Flow Problems
## Concrete Prompt Improvements
## Concrete Recovery Improvements
## Suggested Better Opening Prompt
## Top 3 Highest-Leverage Changes

Every recommendation should be concrete, actionable, and tied to specific message ids or tool calls when possible.`;

let databaseReady = false;

type PromptRow = {
  prompt_id: string;
  name: string;
  description: string | null;
  prompt_text: string;
  is_default: number;
  created_at: string;
  updated_at: string;
};

type EvaluationRow = {
  evaluation_id: string;
  conversation_id: string;
  prompt_id: string | null;
  provider: EvaluationProvider;
  model: string;
  status: "running" | "completed" | "failed";
  scope: EvaluationScope;
  selection_instruction: string | null;
  prompt_name: string;
  prompt_text: string;
  report_markdown: string | null;
  raw_output: string | null;
  error_message: string | null;
  command: string;
  created_at: string;
  finished_at: string | null;
  duration_ms: number | null;
};

export interface EvaluationRequest {
  projectPath: string;
  sessionId: string;
  provider: EvaluationProvider;
  model: string;
  scope: EvaluationScope;
  promptId?: string | null;
  promptName?: string | null;
  promptText: string;
  selectionInstruction?: string | null;
}

interface PersistedEvaluationInput {
  evaluationId: string;
  conversationId: string;
  provider: EvaluationProvider;
  model: string;
  scope: EvaluationScope;
  promptId?: string | null;
  promptName: string;
  promptText: string;
  selectionInstruction?: string | null;
  createdAt: string;
}

function providerForProjectPath(projectPath: string): "claude" | "codex" {
  return projectPath.startsWith("codex:") ? "codex" : "claude";
}

function conversationIdFor(projectPath: string, sessionId: string): string {
  return `${providerForProjectPath(projectPath)}:${sessionId}`;
}

function openDb() {
  ensureDatabaseReady();
  const db = new Database(OLTP_DB_PATH);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  db.pragma("busy_timeout = 5000");
  return db;
}

function ensureDatabaseReady() {
  if (databaseReady) {
    return;
  }

  execFileSync(
    "uv",
    ["run", "alembic", "-c", join(process.cwd(), "alembic.ini"), "-x", "target=oltp", "upgrade", "head"],
    {
      cwd: process.cwd(),
      stdio: "pipe",
    }
  );

  const db = new Database(OLTP_DB_PATH);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  db.pragma("busy_timeout = 5000");
  seedDefaultPrompt(db);
  db.close();
  databaseReady = true;
}

function seedDefaultPrompt(db: Database.Database) {
  const now = new Date().toISOString();
  db.prepare(
    `
      INSERT OR IGNORE INTO evaluation_prompts (
        prompt_id,
        name,
        description,
        prompt_text,
        is_default,
        created_at,
        updated_at
      ) VALUES (?, ?, ?, ?, 1, ?, ?)
    `
  ).run(
    "default-conversation-review",
    DEFAULT_EVALUATION_PROMPT_NAME,
    "Default review prompt for diagnosing instruction quality and conversation flow.",
    DEFAULT_EVALUATION_PROMPT,
    now,
    now
  );
}

function mapPrompt(row: PromptRow): EvaluationPrompt {
  return {
    promptId: row.prompt_id,
    name: row.name,
    description: row.description,
    promptText: row.prompt_text,
    isDefault: Boolean(row.is_default),
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function mapEvaluation(row: EvaluationRow): ConversationEvaluation {
  return {
    evaluationId: row.evaluation_id,
    conversationId: row.conversation_id,
    promptId: row.prompt_id,
    provider: row.provider,
    model: row.model,
    status: row.status,
    scope: row.scope,
    selectionInstruction: row.selection_instruction,
    promptName: row.prompt_name,
    promptText: row.prompt_text,
    reportMarkdown: row.report_markdown,
    rawOutput: row.raw_output,
    errorMessage: row.error_message,
    command: row.command,
    createdAt: row.created_at,
    finishedAt: row.finished_at,
    durationMs: row.duration_ms,
  };
}

function buildEvaluationCommand(
  provider: EvaluationProvider,
  model: string,
  cwd: string
): { binary: string; args: string[]; command: string } {
  if (provider === "claude") {
    const args = ["-p", "--dangerously-skip-permissions", "--model", model];
    return {
      binary: "claude",
      args,
      command: ["claude", ...args].join(" "),
    };
  }

  const args = [
    "exec",
    "--dangerously-bypass-approvals-and-sandbox",
    "--skip-git-repo-check",
    "-C",
    cwd,
    "-m",
    model,
    "-",
  ];
  return {
    binary: "codex",
    args,
    command: ["codex", ...args].join(" "),
  };
}

function decodeWorkspacePath(projectPath: string): string {
  const encoded = projectPath.startsWith("codex:")
    ? projectPath.slice("codex:".length)
    : projectPath;

  if (encoded.startsWith("-")) {
    return encoded.replace(/^-/, "/").replace(/-/g, "/");
  }

  return join(homedir(), encoded);
}

function resolveWorkspace(projectPath: string): string {
  const candidate = decodeWorkspacePath(projectPath);
  if (existsSync(candidate)) {
    return candidate;
  }
  return process.cwd();
}

function formatBlock(messageId: string, block: ProcessedConversation["messages"][number]["blocks"][number]): string {
  if (block.type === "text") {
    return `message ${messageId} text:\n${block.text}`;
  }
  if (block.type === "thinking") {
    return `message ${messageId} thinking:\n${block.thinking}`;
  }

  return [
    `message ${messageId} tool call: ${block.toolName}`,
    `input: ${JSON.stringify(block.input, null, 2)}`,
    block.result ? `result:\n${block.result}` : null,
    block.isError ? "status: failed" : "status: succeeded",
  ]
    .filter(Boolean)
    .join("\n");
}

function renderConversationTranscript(
  conversation: ProcessedConversation,
  scope: EvaluationScope
): string {
  if (scope === "failed_tool_calls") {
    const segments = conversation.messages.flatMap((message, index) => {
      const hasFailure = message.blocks.some(
        (block) => block.type === "tool_call" && block.isError
      );
      if (!hasFailure) {
        return [];
      }

      const contextMessages = [conversation.messages[index - 1], message].filter(Boolean);
      return contextMessages.map((entry) => {
        const blocks = entry.blocks.map((block) => formatBlock(entry.id, block)).join("\n\n");
        return [
          `message_id: ${entry.id}`,
          `role: ${entry.role}`,
          `timestamp: ${new Date(entry.timestamp).toISOString()}`,
          blocks,
        ].join("\n");
      });
    });

    if (segments.length === 0) {
      return "No failed tool calls were captured for this conversation.";
    }

    return segments.join("\n\n---\n\n");
  }

  return conversation.messages
    .map((message) => {
      const blocks = message.blocks.map((block) => formatBlock(message.id, block)).join("\n\n");
      return [
        `message_id: ${message.id}`,
        `role: ${message.role}`,
        `timestamp: ${new Date(message.timestamp).toISOString()}`,
        blocks,
      ].join("\n");
    })
    .join("\n\n---\n\n");
}

function buildEvaluationPrompt(
  conversation: ProcessedConversation,
  scope: EvaluationScope,
  promptText: string,
  selectionInstruction?: string | null
): string {
  const scopeLabel =
    scope === "full"
      ? "the full conversation"
      : scope === "failed_tool_calls"
        ? "only failed tool calls and their nearby context"
        : "a guided subset of the conversation";

  const selectionBlock =
    scope === "guided_subset" && selectionInstruction
      ? `Before writing the report, first isolate only the messages that match this analyst instruction:\n${selectionInstruction}\n\nThen base the report on that subset.`
      : "";

  return [
    "You are evaluating a coding-assistant conversation for quality, instruction design, and flow.",
    "Do not edit files or run commands. Analyze only the provided transcript.",
    `The transcript below contains ${scopeLabel}.`,
    promptText.trim(),
    selectionBlock,
    "Conversation metadata:",
    `- model: ${conversation.model ?? "unknown"}`,
    `- message count: ${conversation.messages.length}`,
    `- sub-agent count: ${conversation.subagents.length}`,
    `- started at: ${new Date(conversation.startTime).toISOString()}`,
    "",
    "Transcript:",
    renderConversationTranscript(conversation, scope),
  ]
    .filter(Boolean)
    .join("\n\n");
}

async function executeEvaluationCommand(
  provider: EvaluationProvider,
  model: string,
  prompt: string,
  cwd: string
): Promise<{ stdout: string; stderr: string; command: string }> {
  const { binary, args, command } = buildEvaluationCommand(provider, model, cwd);

  return new Promise((resolve, reject) => {
    const child = spawn(binary, args, {
      cwd,
      stdio: "pipe",
      env: {
        ...process.env,
        CI: "1",
      },
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve({
          stdout: stdout.trim(),
          stderr: stderr.trim(),
          command,
        });
        return;
      }

      reject(
        new Error(
          stderr.trim() ||
            stdout.trim() ||
            `${binary} exited with status ${code ?? "unknown"}.`
        )
      );
    });

    child.stdin.write(prompt);
    child.stdin.end();
  });
}

function insertRunningEvaluation(
  db: Database.Database,
  input: PersistedEvaluationInput,
  command: string
) {
  db.prepare(
    `
      INSERT INTO conversation_evaluations (
        evaluation_id,
        conversation_id,
        prompt_id,
        provider,
        model,
        status,
        scope,
        selection_instruction,
        prompt_name,
        prompt_text,
        report_markdown,
        raw_output,
        error_message,
        command,
        created_at,
        finished_at,
        duration_ms
      ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, NULL, NULL)
    `
  ).run(
    input.evaluationId,
    input.conversationId,
    input.promptId ?? null,
    input.provider,
    input.model,
    input.scope,
    input.selectionInstruction ?? null,
    input.promptName,
    input.promptText,
    command,
    input.createdAt
  );
}

function getEvaluationById(db: Database.Database, evaluationId: string) {
  return mapEvaluation(
    db.prepare(
      `
        SELECT
          evaluation_id,
          conversation_id,
          prompt_id,
          provider,
          model,
          status,
          scope,
          selection_instruction,
          prompt_name,
          prompt_text,
          report_markdown,
          raw_output,
          error_message,
          command,
          created_at,
          finished_at,
          duration_ms
        FROM conversation_evaluations
        WHERE evaluation_id = ?
      `
    ).get(evaluationId) as EvaluationRow
  );
}

async function runConversationEvaluationJob(args: {
  evaluationId: string;
  provider: EvaluationProvider;
  model: string;
  prompt: string;
  workspace: string;
  fallbackCommand: string;
}) {
  const startedAt = Date.now();

  try {
    const result = await executeEvaluationCommand(
      args.provider,
      args.model,
      args.prompt,
      args.workspace
    );
    const db = openDb();
    try {
      db.prepare(
        `
          UPDATE conversation_evaluations
          SET
            status = 'completed',
            report_markdown = ?,
            raw_output = ?,
            command = ?,
            finished_at = ?,
            duration_ms = ?
          WHERE evaluation_id = ?
        `
      ).run(
        result.stdout,
        result.stdout,
        result.command,
        new Date().toISOString(),
        Date.now() - startedAt,
        args.evaluationId
      );
    } finally {
      db.close();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Evaluation failed.";
    const db = openDb();
    try {
      db.prepare(
        `
          UPDATE conversation_evaluations
          SET
            status = 'failed',
            error_message = ?,
            command = ?,
            finished_at = ?,
            duration_ms = ?
          WHERE evaluation_id = ?
        `
      ).run(
        message,
        args.fallbackCommand,
        new Date().toISOString(),
        Date.now() - startedAt,
        args.evaluationId
      );
    } finally {
      db.close();
    }
  }
}

export function listEvaluationPrompts(): EvaluationPrompt[] {
  const db = openDb();
  try {
    const rows = db
      .prepare(
        `
          SELECT prompt_id, name, description, prompt_text, is_default, created_at, updated_at
          FROM evaluation_prompts
          ORDER BY is_default DESC, updated_at DESC, name ASC
        `
      )
      .all() as PromptRow[];
    return rows.map(mapPrompt);
  } finally {
    db.close();
  }
}

export function createEvaluationPrompt(input: {
  name: string;
  description?: string | null;
  promptText: string;
}): EvaluationPrompt {
  const db = openDb();
  const now = new Date().toISOString();
  const promptId = randomUUID();

  try {
    db.prepare(
      `
        INSERT INTO evaluation_prompts (
          prompt_id,
          name,
          description,
          prompt_text,
          is_default,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, 0, ?, ?)
      `
    ).run(promptId, input.name, input.description ?? null, input.promptText, now, now);

    return mapPrompt(
      db.prepare(
        `
          SELECT prompt_id, name, description, prompt_text, is_default, created_at, updated_at
          FROM evaluation_prompts
          WHERE prompt_id = ?
        `
      ).get(promptId) as PromptRow
    );
  } finally {
    db.close();
  }
}

export function updateEvaluationPrompt(
  promptId: string,
  input: {
    name: string;
    description?: string | null;
    promptText: string;
  }
): EvaluationPrompt {
  const db = openDb();
  const now = new Date().toISOString();

  try {
    db.prepare(
      `
        UPDATE evaluation_prompts
        SET name = ?, description = ?, prompt_text = ?, updated_at = ?
        WHERE prompt_id = ?
      `
    ).run(input.name, input.description ?? null, input.promptText, now, promptId);

    return mapPrompt(
      db.prepare(
        `
          SELECT prompt_id, name, description, prompt_text, is_default, created_at, updated_at
          FROM evaluation_prompts
          WHERE prompt_id = ?
        `
      ).get(promptId) as PromptRow
    );
  } finally {
    db.close();
  }
}

export function deleteEvaluationPrompt(promptId: string) {
  const db = openDb();

  try {
    const row = db
      .prepare("SELECT is_default FROM evaluation_prompts WHERE prompt_id = ?")
      .get(promptId) as { is_default: number } | undefined;

    if (!row) {
      throw new Error("Prompt not found.");
    }

    if (row.is_default) {
      throw new Error("The default prompt cannot be deleted.");
    }

    db.prepare("DELETE FROM evaluation_prompts WHERE prompt_id = ?").run(promptId);
  } finally {
    db.close();
  }
}

export function listConversationEvaluations(conversationId: string): ConversationEvaluation[] {
  const db = openDb();
  try {
    const rows = db
      .prepare(
        `
          SELECT
            evaluation_id,
            conversation_id,
            prompt_id,
            provider,
            model,
            status,
            scope,
            selection_instruction,
            prompt_name,
            prompt_text,
            report_markdown,
            raw_output,
            error_message,
            command,
            created_at,
            finished_at,
            duration_ms
          FROM conversation_evaluations
          WHERE conversation_id = ?
          ORDER BY created_at DESC
        `
      )
      .all(conversationId) as EvaluationRow[];

    return rows.map(mapEvaluation);
  } finally {
    db.close();
  }
}

export async function createConversationEvaluation(
  input: EvaluationRequest
): Promise<ConversationEvaluation> {
  const conversation = await getConversation(input.projectPath, input.sessionId);
  if (!conversation) {
    throw new Error("Conversation not found.");
  }

  const conversationId = conversationIdFor(input.projectPath, input.sessionId);
  const promptName = (input.promptName || DEFAULT_EVALUATION_PROMPT_NAME).trim();
  const promptText = input.promptText.trim();
  if (!promptName || !promptText) {
    throw new Error("Prompt name and prompt text are required.");
  }

  const db = openDb();
  const evaluationId = randomUUID();
  const createdAt = new Date().toISOString();
  const workspace = resolveWorkspace(input.projectPath);
  const fullPrompt = buildEvaluationPrompt(
    conversation,
    input.scope,
    promptText,
    input.selectionInstruction
  );
  const { command } = buildEvaluationCommand(input.provider, input.model, workspace);

  let evaluation: ConversationEvaluation;
  try {
    insertRunningEvaluation(
      db,
      {
        evaluationId,
        conversationId,
        promptId: input.promptId ?? null,
        provider: input.provider,
        model: input.model,
        scope: input.scope,
        selectionInstruction: input.selectionInstruction ?? null,
        promptName,
        promptText,
        createdAt,
      },
      command
    );
    evaluation = getEvaluationById(db, evaluationId);
  } finally {
    db.close();
  }

  void runConversationEvaluationJob({
    evaluationId,
    provider: input.provider,
    model: input.model,
    prompt: fullPrompt,
    workspace,
    fallbackCommand: command,
  });

  return evaluation;
}
