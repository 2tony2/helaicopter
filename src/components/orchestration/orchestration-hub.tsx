"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConversationDagList } from "@/components/conversation/conversation-dag-list";
import { OvernightOatsPanel } from "./overnight-oats-panel";
import { useOvernightOatsRuns } from "@/hooks/use-conversations";

export function OrchestrationHub({
  initialTab = "conversation-dags",
}: {
  initialTab?: "conversation-dags" | "oats";
}) {
  const { data: oatsRuns } = useOvernightOatsRuns();
  const oatsCount = oatsRuns?.length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Orchestration</h1>
        <p className="mt-1 text-muted-foreground">
          DAGs for conversation sub-agents and Overnight Oats task orchestration.
        </p>
      </div>

      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="conversation-dags">Conversation DAGs</TabsTrigger>
          <TabsTrigger value="oats">
            Overnight Oats {oatsCount > 0 ? `(${oatsCount})` : ""}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="conversation-dags">
          <ConversationDagList />
        </TabsContent>

        <TabsContent value="oats">
          <OvernightOatsPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
