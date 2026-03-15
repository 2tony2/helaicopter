"use client";

import { useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { useEvaluationPrompts } from "@/hooks/use-conversations";
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

function toDraftPrompt(prompt: {
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
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null);
  const [draftPromptId, setDraftPromptId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftPrompt>(EMPTY_DRAFT);
  const [error, setError] = useState<string | null>(null);
  const prompts = data ?? [];
  const effectiveSelectedPromptId =
    selectedPromptId && prompts.some((prompt) => prompt.promptId === selectedPromptId)
      ? selectedPromptId
      : prompts[0]?.promptId ?? null;
  const selectedPrompt =
    prompts.find((prompt) => prompt.promptId === effectiveSelectedPromptId) ?? null;
  const activeDraft =
    draftPromptId === effectiveSelectedPromptId
      ? draft
      : selectedPrompt
        ? toDraftPrompt(selectedPrompt)
        : EMPTY_DRAFT;

  async function savePrompt() {
    setError(null);
    const payload = {
      name: activeDraft.name.trim(),
      description: activeDraft.description.trim(),
      promptText: activeDraft.promptText.trim(),
    };

    if (!payload.name || !payload.promptText) {
      setError("Name and prompt text are required.");
      return;
    }

    const url = selectedPrompt
      ? `/api/evaluation-prompts/${selectedPrompt.promptId}`
      : "/api/evaluation-prompts";
    const method = selectedPrompt ? "PATCH" : "POST";

    const response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const body = await response.json();
    if (!response.ok) {
      setError(body.error ?? "Failed to save prompt.");
      return;
    }

    await mutate();
    setSelectedPromptId(body.promptId);
    setDraftPromptId(body.promptId);
    setDraft({
      name: payload.name,
      description: payload.description,
      promptText: payload.promptText,
    });
  }

  async function deletePrompt() {
    if (!selectedPrompt) {
      return;
    }

    setError(null);
    const response = await fetch(`/api/evaluation-prompts/${selectedPrompt.promptId}`, {
      method: "DELETE",
    });
    const body = await response.json();
    if (!response.ok) {
      setError(body.error ?? "Failed to delete prompt.");
      return;
    }

    await mutate();
    setSelectedPromptId(null);
    setDraftPromptId(null);
    setDraft(EMPTY_DRAFT);
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
              setDraftPromptId(null);
              setDraft(EMPTY_DRAFT);
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
                prompt.promptId === effectiveSelectedPromptId
                  ? "border-primary bg-accent/60"
                  : "hover:bg-accent/40"
              }`}
              onClick={() => {
                setSelectedPromptId(prompt.promptId);
                setDraftPromptId(prompt.promptId);
                setDraft(toDraftPrompt(prompt));
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
              value={activeDraft.name}
              onChange={(event) => {
                setDraftPromptId(effectiveSelectedPromptId);
                setDraft({
                  ...activeDraft,
                  name: event.target.value,
                });
              }}
              placeholder="Prompt name"
            />
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">Description</div>
            <Input
              value={activeDraft.description}
              onChange={(event) => {
                setDraftPromptId(effectiveSelectedPromptId);
                setDraft({
                  ...activeDraft,
                  description: event.target.value,
                });
              }}
              placeholder="Short description"
            />
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">Prompt</div>
            <Textarea
              className="min-h-[360px]"
              value={activeDraft.promptText}
              onChange={(event) => {
                setDraftPromptId(effectiveSelectedPromptId);
                setDraft({
                  ...activeDraft,
                  promptText: event.target.value,
                });
              }}
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
