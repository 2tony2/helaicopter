"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConversationDagList } from "@/components/conversation/conversation-dag-list";
import { OvernightOatsPanel } from "./overnight-oats-panel";
import { usePrefectFlowRuns } from "@/hooks/use-conversations";

export function OrchestrationHub({
  initialTab = "prefect",
}: {
  initialTab?: "conversation-dags" | "prefect";
}) {
  const { data: prefectFlowRuns } = usePrefectFlowRuns();
  const prefectCount = prefectFlowRuns?.length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Orchestration</h1>
        <p className="mt-1 text-muted-foreground">
          Prefect-native orchestration status, worker health, and legacy Oats run records.
        </p>
      </div>

      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="conversation-dags">Conversation DAGs</TabsTrigger>
          <TabsTrigger value="prefect">
            Prefect {prefectCount > 0 ? `(${prefectCount})` : ""}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="conversation-dags">
          <ConversationDagList />
        </TabsContent>

        <TabsContent value="prefect">
          <OvernightOatsPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
