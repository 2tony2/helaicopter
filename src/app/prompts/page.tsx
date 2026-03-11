import type { Metadata } from "next";
import { PromptManager } from "@/components/evaluations/prompt-manager";

export const metadata: Metadata = {
  title: "Prompts | Helaicopter",
  description: "Create and manage saved conversation evaluation prompts.",
};

export default function PromptsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Evaluation Prompts</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Save reusable evaluation prompts for Claude and Codex. Prompts are stored in the
          SQLite OLTP database and can be selected from the conversation evaluator.
        </p>
      </div>
      <PromptManager />
    </div>
  );
}
