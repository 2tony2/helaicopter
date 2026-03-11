import { NextResponse } from "next/server";
import { createConversationEvaluation, listConversationEvaluations } from "@/lib/evaluations";
import type { EvaluationProvider, EvaluationScope } from "@/lib/evaluation-models";

function providerForProjectPath(projectPath: string): "claude" | "codex" {
  return projectPath.startsWith("codex:") ? "codex" : "claude";
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ projectPath: string; sessionId: string }> }
) {
  const { projectPath, sessionId } = await params;
  const decodedProjectPath = decodeURIComponent(projectPath);
  const conversationId = `${providerForProjectPath(decodedProjectPath)}:${sessionId}`;
  return NextResponse.json(listConversationEvaluations(conversationId));
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ projectPath: string; sessionId: string }> }
) {
  const { projectPath, sessionId } = await params;
  const decodedProjectPath = decodeURIComponent(projectPath);
  const body = await request.json();

  const provider = body.provider as EvaluationProvider;
  const model = String(body.model ?? "").trim();
  const promptText = String(body.promptText ?? "").trim();
  const promptName = String(body.promptName ?? "").trim();
  const scope = body.scope as EvaluationScope;
  const selectionInstruction =
    typeof body.selectionInstruction === "string"
      ? body.selectionInstruction.trim()
      : null;
  const promptId =
    typeof body.promptId === "string" && body.promptId.trim()
      ? body.promptId.trim()
      : null;

  if (!provider || !model || !promptText || !promptName || !scope) {
    return NextResponse.json(
      { error: "Provider, model, prompt, and scope are required." },
      { status: 400 }
    );
  }

  try {
    const evaluation = await createConversationEvaluation({
      projectPath: decodedProjectPath,
      sessionId,
      provider,
      model,
      promptId,
      promptName,
      promptText,
      scope,
      selectionInstruction,
    });
    return NextResponse.json(evaluation, { status: 202 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to evaluate conversation.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
