"use client";

import { useMemo, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { useEvaluationPrompts } from "@/hooks/use-conversations";
import {
  createEvaluationPrompt,
  deleteEvaluationPrompt,
  updateEvaluationPrompt,
} from "@/lib/client/mutations";
import {
  formatEvaluationValidationError,
  parseEvaluationPromptWriteInput,
} from "@/lib/client/schemas/evaluations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type DraftPrompt = {
  name: string;
  description: string;
  promptText: string;
};

const EMPTY_DRAFT: DraftPrompt = {
  name: "",
  description: "",
  promptText: "",
};

function draftFromPrompt(prompt: {
  promptId: string;
  name: string;
  description?: string | null;
  promptText: string;
}): DraftPrompt {
  return {
    name: prompt.name,
    description: prompt.description ?? "",
    promptText: prompt.promptText,
  };
}

export function PromptManager() {
  const { data, isLoading, mutate } = useEvaluationPrompts();
  const [selectedPromptId, setSelectedPromptId] = useState<string | null | undefined>(
    undefined
  );
  const [draftState, setDraftState] = useState<{
    sourcePromptId: string | null;
    value: DraftPrompt;
  }>({
    sourcePromptId: null,
    value: EMPTY_DRAFT,
  });
  const [error, setError] = useState<string | null>(null);
  const prompts = useMemo(() => data ?? [], [data]);
  const selectedPrompt = useMemo(() => {
    if (selectedPromptId === null) {
      return null;
    }

    if (!selectedPromptId) {
      return prompts[0] ?? null;
    }

    return (
      prompts.find((prompt) => prompt.promptId === selectedPromptId) ??
      prompts[0] ??
      null
    );
  }, [prompts, selectedPromptId]);
  const activePromptId = selectedPrompt?.promptId ?? null;
  const draft = useMemo(() => {
    if (draftState.sourcePromptId === activePromptId) {
      return draftState.value;
    }

    if (selectedPrompt) {
      return draftFromPrompt(selectedPrompt);
    }

    return EMPTY_DRAFT;
  }, [activePromptId, draftState, selectedPrompt]);

  function updateDraft(nextDraft: DraftPrompt) {
    setDraftState({
      sourcePromptId: activePromptId,
      value: nextDraft,
    });
  }

  async function savePrompt() {
    setError(null);
    let payload: ReturnType<typeof parseEvaluationPromptWriteInput>;

    try {
      payload = parseEvaluationPromptWriteInput({
        name: draft.name,
        description: draft.description,
        promptText: draft.promptText,
      });
    } catch (error) {
      setError(formatEvaluationValidationError(error, "Name and prompt text are required."));
      return;
    }

    let body: { promptId: string };

    try {
      body = selectedPrompt
        ? await updateEvaluationPrompt(selectedPrompt.promptId, payload)
        : await createEvaluationPrompt(payload);
    } catch (error) {
      setError(formatEvaluationValidationError(error, "Failed to save prompt."));
      return;
    }

    await mutate();
    setSelectedPromptId(body.promptId);
    setDraftState({
      sourcePromptId: body.promptId,
      value: {
        ...payload,
        description: payload.description ?? "",
      },
    });
  }

  async function deletePrompt() {
    if (!selectedPrompt) {
      return;
    }

    setError(null);
    try {
      await deleteEvaluationPrompt(selectedPrompt.promptId);
    } catch (error) {
      setError(formatEvaluationValidationError(error, "Failed to delete prompt."));
      return;
    }

    await mutate();
    setSelectedPromptId(undefined);
    setDraftState({
      sourcePromptId: null,
      value: EMPTY_DRAFT,
    });
  }

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">Loading prompts...</div>;
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Saved Prompts</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setSelectedPromptId(null);
              setDraftState({
                sourcePromptId: null,
                value: EMPTY_DRAFT,
              });
              setError(null);
            }}
          >
            <Plus className="h-4 w-4" />
            New
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {prompts.map((prompt) => (
            <button
              key={prompt.promptId}
              className={`w-full rounded-lg border p-3 text-left transition-colors ${
                prompt.promptId === activePromptId
                  ? "border-primary bg-accent/60"
                  : "hover:bg-accent/40"
              }`}
              onClick={() => {
                setSelectedPromptId(prompt.promptId);
                setDraftState({
                  sourcePromptId: prompt.promptId,
                  value: draftFromPrompt(prompt),
                });
                setError(null);
              }}
            >
              <div className="flex items-center gap-2">
                <div className="font-medium text-sm">{prompt.name}</div>
                {prompt.isDefault && (
                  <Badge variant="secondary" className="text-[10px]">
                    Default
                  </Badge>
                )}
              </div>
              {prompt.description && (
                <div className="mt-1 text-xs text-muted-foreground line-clamp-2">
                  {prompt.description}
                </div>
              )}
            </button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {selectedPrompt ? "Edit Prompt" : "Create Prompt"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="text-sm font-medium">Name</div>
            <Input
              value={draft.name}
              onChange={(event) =>
                updateDraft({ ...draft, name: event.target.value })
              }
              placeholder="Prompt name"
            />
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">Description</div>
            <Input
              value={draft.description}
              onChange={(event) =>
                updateDraft({ ...draft, description: event.target.value })
              }
              placeholder="Short description"
            />
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">Prompt</div>
            <Textarea
              className="min-h-[360px]"
              value={draft.promptText}
              onChange={(event) =>
                updateDraft({ ...draft, promptText: event.target.value })
              }
              placeholder="Write the evaluation prompt here"
            />
          </div>

          {error && <div className="text-sm text-destructive">{error}</div>}

          <div className="flex items-center justify-between gap-3">
            <Button onClick={() => void savePrompt()}>
              <Save className="h-4 w-4" />
              Save Prompt
            </Button>
            {selectedPrompt && !selectedPrompt.isDefault && (
              <Button variant="outline" onClick={() => void deletePrompt()}>
                <Trash2 className="h-4 w-4" />
                Delete Prompt
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
