"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConversationDagList } from "@/components/conversation/conversation-dag-list";
import { OvernightOatsPanel } from "./overnight-oats-panel";
import type { OrchestrationTab } from "./tabs";
import { PageHeader } from "@/components/layout/page-header";

export function OrchestrationHub({
  initialTab = "orchestration",
}: {
  initialTab?: OrchestrationTab;
}) {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Orchestration"
        description="Overnight Oats runs and conversation DAG relationships."
      />

      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="conversation-dags">Conversation DAGs</TabsTrigger>
          <TabsTrigger value="orchestration">Orchestration</TabsTrigger>
        </TabsList>

        <TabsContent value="conversation-dags">
          <ConversationDagList />
        </TabsContent>

        <TabsContent value="orchestration">
          <OvernightOatsPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
