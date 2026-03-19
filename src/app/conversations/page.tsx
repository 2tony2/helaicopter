"use client";

import { ConversationList } from "@/components/conversation/conversation-list";
import { PageHeader } from "@/components/layout/page-header";

export default function ConversationsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Conversations"
        description="Browse all conversation threads, including main runs and sub-agents"
      />
      <ConversationList />
    </div>
  );
}
