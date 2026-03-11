import { NextResponse } from "next/server";
import {
  createEvaluationPrompt,
  listEvaluationPrompts,
} from "@/lib/evaluations";

export async function GET() {
  return NextResponse.json(listEvaluationPrompts());
}

export async function POST(request: Request) {
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
    const prompt = createEvaluationPrompt({
      name,
      promptText,
      description,
    });
    return NextResponse.json(prompt, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to create prompt.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
