import assert from "node:assert/strict";
import test from "node:test";

async function getSchemas() {
  return import(new URL("./evaluations.ts", import.meta.url).href);
}

test("parseEvaluationPromptWriteInput trims name, description, and prompt text", async () => {
  const { parseEvaluationPromptWriteInput } = await getSchemas();
  const payload = parseEvaluationPromptWriteInput({
    name: "  Reviewer Sweep  ",
    description: "  Focus on failing turns  ",
    promptText: "  Review the weakest turns.  ",
  });

  assert.deepEqual(payload, {
    name: "Reviewer Sweep",
    description: "Focus on failing turns",
    promptText: "Review the weakest turns.",
  });
});

test("parseEvaluationPromptWriteInput rejects blank required fields", async () => {
  const { parseEvaluationPromptWriteInput } = await getSchemas();
  assert.throws(
    () =>
      parseEvaluationPromptWriteInput({
        name: "   ",
        description: "Optional details",
        promptText: "  Review the weakest turns. ",
      }),
    /name/i
  );

  assert.throws(
    () =>
      parseEvaluationPromptWriteInput({
        name: "Reviewer Sweep",
        description: "Optional details",
        promptText: "   ",
      }),
    /promptText/i
  );
});

test("parseConversationEvaluationCreateInput requires a selection instruction for guided subsets", async () => {
  const { parseConversationEvaluationCreateInput } = await getSchemas();
  assert.throws(
    () =>
      parseConversationEvaluationCreateInput({
        provider: "codex",
        model: "gpt-5",
        selectedPromptId: "prompt-1",
        promptName: "Reviewer Sweep",
        promptText: "Review the weakest turns.",
        scope: "guided_subset",
        selectionInstruction: "   ",
      }),
    /selectionInstruction/i
  );
});

test("parseConversationEvaluationCreateInput normalizes custom prompts and trims fields", async () => {
  const { parseConversationEvaluationCreateInput } = await getSchemas();
  const payload = parseConversationEvaluationCreateInput({
    provider: "codex",
    model: "gpt-5",
    selectedPromptId: "custom",
    promptName: "  Custom Conversation Review ",
    promptText: "  Review the weakest turns. ",
    scope: "full",
    selectionInstruction: " ignored when scope is full ",
  });

  assert.deepEqual(payload, {
    provider: "codex",
    model: "gpt-5",
    promptId: null,
    promptName: "Custom Conversation Review",
    promptText: "Review the weakest turns.",
    scope: "full",
    selectionInstruction: null,
  });
});

test("parseConversationEvaluationCreateInput rejects blank custom prompt content", async () => {
  const { parseConversationEvaluationCreateInput } = await getSchemas();
  assert.throws(
    () =>
      parseConversationEvaluationCreateInput({
        provider: "codex",
        model: "gpt-5",
        selectedPromptId: "custom",
        promptName: "   ",
        promptText: "Review the weakest turns.",
        scope: "full",
        selectionInstruction: "",
      }),
    /promptName/i
  );
});
