"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConversationDagList } from "@/components/conversation/conversation-dag-list";
import { OvernightOatsPanel } from "./overnight-oats-panel";
import { PrefectUiEmbed } from "./prefect-ui-embed";
import type { OrchestrationTab } from "./tabs";
import { PageHeader } from "@/components/layout/page-header";

export function OrchestrationHub({
  initialTab = "orchestration",
  prefectPath,
}: {
  initialTab?: OrchestrationTab;
  prefectPath?: string;
}) {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Orchestration"
        description="Overnight Oats runs, conversation DAG relationships, and Prefect UI."
      />

      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="conversation-dags">Conversation DAGs</TabsTrigger>
          <TabsTrigger value="orchestration">Orchestration</TabsTrigger>
          <TabsTrigger value="prefect-ui">Prefect UI</TabsTrigger>
        </TabsList>

        <TabsContent value="conversation-dags">
          <ConversationDagList />
        </TabsContent>

        <TabsContent value="orchestration">
          <OvernightOatsPanel />
        </TabsContent>

        <TabsContent value="prefect-ui">
          <PrefectUiEmbed prefectPath={prefectPath} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
