import type { Metadata } from "next";
import { PromptManager } from "@/components/evaluations/prompt-manager";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "Prompts | Helaicopter",
  description: "Create and manage saved conversation evaluation prompts.",
};

export default function PromptsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Evaluation Prompts"
        description={
          <span className="max-w-3xl block">
            Save reusable evaluation prompts for Claude and Codex. Prompts are stored in the
            SQLite OLTP database and can be selected from the conversation evaluator.
          </span>
        }
      />
      <PromptManager />
    </div>
  );
}
