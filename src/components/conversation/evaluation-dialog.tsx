"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { useEvaluationPrompts } from "@/hooks/use-conversations";
import { createConversationEvaluation } from "@/lib/client/mutations";
import {
  formatEvaluationValidationError,
  parseConversationEvaluationCreateInput,
} from "@/lib/client/schemas/evaluations";
import type { ConversationEvaluation } from "@/lib/types";
import {
  CLAUDE_EVALUATION_MODELS,
  CODEX_EVALUATION_MODELS,
  type EvaluationProvider,
  type EvaluationScope,
} from "@/lib/evaluation-models";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type EvaluationDialogProps = {
  projectPath: string;
  sessionId: string;
  onCreated: (evaluation: ConversationEvaluation) => void;
  onSubmitted?: () => void;
};

export function EvaluationDialog({
  projectPath,
  sessionId,
  onCreated,
  onSubmitted,
}: EvaluationDialogProps) {
  const { data: prompts } = useEvaluationPrompts();
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState<EvaluationProvider>("codex");
  const [model, setModel] = useState(CODEX_EVALUATION_MODELS[0]);
  const [selectedPromptId, setSelectedPromptId] = useState<string>("custom");
  const [promptName, setPromptName] = useState("Custom Conversation Review");
  const [promptText, setPromptText] = useState("");
  const [scope, setScope] = useState<EvaluationScope>("full");
  const [selectionInstruction, setSelectionInstruction] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const availableModels = useMemo(
    () => (provider === "claude" ? CLAUDE_EVALUATION_MODELS : CODEX_EVALUATION_MODELS),
    [provider]
  );

  useEffect(() => {
    setModel(availableModels[0]);
  }, [availableModels]);

  useEffect(() => {
    if (!prompts?.length || promptText) {
      return;
    }

    const defaultPrompt = prompts[0];
    setSelectedPromptId(defaultPrompt.promptId);
    setPromptName(defaultPrompt.name);
    setPromptText(defaultPrompt.promptText);
  }, [prompts, promptText]);

  function applyPrompt(promptId: string) {
    setSelectedPromptId(promptId);
    if (promptId === "custom") {
      setPromptName("Custom Conversation Review");
      return;
    }

    const prompt = prompts?.find((entry) => entry.promptId === promptId);
    if (!prompt) {
      return;
    }

    setPromptName(prompt.name);
    setPromptText(prompt.promptText);
  }

  async function submitEvaluation() {
    setError(null);
    setIsSubmitting(true);

    try {
      const input = parseConversationEvaluationCreateInput({
        provider,
        model,
        selectedPromptId,
        promptName,
        promptText,
        scope,
        selectionInstruction,
      });
      const body = await createConversationEvaluation(projectPath, sessionId, input);

      onCreated(body);
      onSubmitted?.();
      setOpen(false);
    } catch (error) {
      setError(formatEvaluationValidationError(error, "Failed to evaluate conversation."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Sparkles className="h-4 w-4" />
          Evaluate Conversation
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Evaluate Conversation</DialogTitle>
          <DialogDescription>
            Run Claude or Codex against this conversation and store the report in SQLite.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <div className="text-sm font-medium">Model Provider</div>
              <select
                value={provider}
                onChange={(event) => setProvider(event.target.value as EvaluationProvider)}
                className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
              >
                <option value="claude">Claude</option>
                <option value="codex">Codex</option>
              </select>
            </div>
            <div className="space-y-2">
              <div className="text-sm font-medium">Model</div>
              <select
                value={model}
                onChange={(event) => setModel(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
              >
                {availableModels.map((entry) => (
                  <option key={entry} value={entry}>
                    {entry}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_180px]">
            <div className="space-y-2">
              <div className="text-sm font-medium">Prompt Name</div>
              <Input
                value={promptName}
                onChange={(event) => setPromptName(event.target.value)}
                placeholder="Evaluation prompt name"
              />
            </div>
            <div className="space-y-2">
              <div className="text-sm font-medium">Saved Prompt</div>
              <select
                value={selectedPromptId}
                onChange={(event) => applyPrompt(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
              >
                <option value="custom">Custom</option>
                {prompts?.map((prompt) => (
                  <option key={prompt.promptId} value={prompt.promptId}>
                    {prompt.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium">Evaluation Prompt</div>
            <Textarea
              className="min-h-[220px]"
              value={promptText}
              onChange={(event) => setPromptText(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium">Conversation Scope</div>
            <select
              value={scope}
              onChange={(event) => setScope(event.target.value as EvaluationScope)}
              className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            >
              <option value="full">Whole conversation</option>
              <option value="failed_tool_calls">Failed tool calls only</option>
              <option value="guided_subset">Guided subset with instruction</option>
            </select>
          </div>

          {scope === "guided_subset" && (
            <div className="space-y-2">
              <div className="text-sm font-medium">Message Selection Instruction</div>
              <Textarea
                className="min-h-28"
                value={selectionInstruction}
                onChange={(event) => setSelectionInstruction(event.target.value)}
                placeholder="Example: focus on the messages around the first failing Bash tool call and the assistant's recovery strategy."
              />
            </div>
          )}

          {error && <div className="text-sm text-destructive">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={() => void submitEvaluation()} disabled={isSubmitting}>
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Run Evaluation
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
