"use client";

import { ConversationList } from "@/components/conversation/conversation-list";

export default function ConversationsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Conversations</h1>
        <p className="text-muted-foreground mt-1">
          Browse all Claude Code conversations
        </p>
      </div>
      <ConversationList />
    </div>
  );
}
