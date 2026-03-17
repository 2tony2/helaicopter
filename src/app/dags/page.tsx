"use client";

import { ConversationDagList } from "@/components/conversation/conversation-dag-list";

export default function DagsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Sub-agent DAGs</h1>
        <p className="mt-1 text-muted-foreground">
          Main conversations that spawned sub-agents, with depth, breadth, and graph totals.
        </p>
      </div>
      <ConversationDagList />
    </div>
  );
}
