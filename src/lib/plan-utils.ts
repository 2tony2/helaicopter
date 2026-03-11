import type {
  ConversationPlanStep,
  PlanSummary,
} from "./types";

export type PlanSource =
  | { kind: "file"; slug: string }
  | {
      kind: "claude-session";
      projectPath: string;
      sessionId: string;
      eventId: string;
    }
  | {
      kind: "codex-session";
      sessionId: string;
      callId: string;
    };

export function toEpochMs(ts: string | number | undefined): number {
  if (typeof ts === "number") return ts;
  if (typeof ts === "string") return new Date(ts).getTime();
  return 0;
}

export function encodePlanId(source: PlanSource): string {
  return Buffer.from(JSON.stringify(source)).toString("base64url");
}

export function decodePlanId(id: string): PlanSource | null {
  try {
    const parsed = JSON.parse(
      Buffer.from(id, "base64url").toString("utf-8")
    ) as PlanSource;
    if (parsed.kind === "file" && parsed.slug) return parsed;
    if (
      parsed.kind === "claude-session" &&
      parsed.projectPath &&
      parsed.sessionId &&
      parsed.eventId
    ) {
      return parsed;
    }
    if (parsed.kind === "codex-session" && parsed.sessionId && parsed.callId) {
      return parsed;
    }
  } catch {
    // Fall through to legacy file-based IDs.
  }

  if (id) {
    return { kind: "file", slug: id };
  }

  return null;
}

export function summarizePlanContent(
  content: string,
  fallbackSlug: string
): Pick<PlanSummary, "slug" | "title" | "preview"> {
  const lines = content.split("\n").filter((line) => line.trim());
  const title =
    lines.find((line) => line.startsWith("# "))?.replace(/^#\s+/, "") ||
    fallbackSlug;
  const preview = lines
    .filter((line) => !line.startsWith("#"))
    .slice(0, 3)
    .join(" ")
    .slice(0, 200);

  return {
    slug: fallbackSlug,
    title,
    preview,
  };
}

function truncate(text: string, maxLength = 80): string {
  return text.length > maxLength
    ? `${text.slice(0, maxLength - 3).trimEnd()}...`
    : text;
}

function slugify(value: string): string {
  const slug = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "plan";
}

function checkboxForStatus(status: string): string {
  if (status === "completed") return "[x]";
  if (status === "in_progress") return "[-]";
  return "[ ]";
}

export function parseCodexPlanSteps(
  rawPlan: unknown
): ConversationPlanStep[] {
  if (!Array.isArray(rawPlan)) return [];

  return rawPlan
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null;
      const step = "step" in entry ? entry.step : undefined;
      const status = "status" in entry ? entry.status : undefined;
      if (typeof step !== "string" || !step.trim()) return null;
      return {
        step: step.trim(),
        status: typeof status === "string" && status.trim() ? status.trim() : "pending",
      };
    })
    .filter((entry): entry is ConversationPlanStep => entry !== null);
}

export function summarizeCodexPlan(
  args: Record<string, unknown>,
  callId: string
): {
  slug: string;
  title: string;
  preview: string;
  content: string;
  explanation?: string;
  steps: ConversationPlanStep[];
} {
  const explanation =
    typeof args.explanation === "string" && args.explanation.trim()
      ? args.explanation.trim()
      : undefined;
  const steps = parseCodexPlanSteps(args.plan);
  const titleSource =
    explanation?.split("\n").find((line) => line.trim()) ||
    steps[0]?.step ||
    `Plan update ${callId.slice(-8)}`;
  const title = truncate(titleSource.trim());
  const slug = `codex-${slugify(title)}-${callId.slice(-8)}`;

  const contentLines = [`# ${title}`];
  if (explanation) {
    contentLines.push("", explanation);
  }
  if (steps.length > 0) {
    contentLines.push("", "## Steps", "");
    for (const step of steps) {
      contentLines.push(`${checkboxForStatus(step.status)} ${step.step}`);
    }
  }
  const content = contentLines.join("\n");
  const preview = summarizePlanContent(content, slug).preview;

  return {
    slug,
    title,
    preview,
    content,
    explanation,
    steps,
  };
}
