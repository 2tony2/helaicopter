import { NextResponse } from "next/server";
import {
  deleteEvaluationPrompt,
  updateEvaluationPrompt,
} from "@/lib/evaluations";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ promptId: string }> }
) {
  const { promptId } = await params;
  const body = await request.json();
  const name = String(body.name ?? "").trim();
  const promptText = String(body.promptText ?? "").trim();
  const description =
    typeof body.description === "string" ? body.description.trim() : null;

  if (!name || !promptText) {
    return NextResponse.json(
      { error: "Name and prompt text are required." },
      { status: 400 }
    );
  }

  try {
    const prompt = updateEvaluationPrompt(promptId, {
      name,
      promptText,
      description,
    });
    return NextResponse.json(prompt);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to update prompt.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ promptId: string }> }
) {
  const { promptId } = await params;

  try {
    deleteEvaluationPrompt(promptId);
    return NextResponse.json({ ok: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to delete prompt.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
