import { ConversationDagList } from "@/components/conversation/conversation-dag-list";
import { PageHeader } from "@/components/layout/page-header";

export default function DagsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Conversation DAGs"
        description="Conversation relationship graphs across Claude, Codex, and OpenClaw sessions."
      />
      <ConversationDagList />
    </div>
  );
}
