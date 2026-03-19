"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConversationDagList } from "@/components/conversation/conversation-dag-list";
import { OvernightOatsPanel } from "./overnight-oats-panel";
import { PrefectUiEmbed } from "./prefect-ui-embed";
import type { OrchestrationTab } from "./tabs";
import { usePrefectFlowRuns } from "@/hooks/use-conversations";
import { PageHeader } from "@/components/layout/page-header";

export function OrchestrationHub({
  initialTab = "prefect",
}: {
  initialTab?: OrchestrationTab;
}) {
  const { data: prefectFlowRuns } = usePrefectFlowRuns();
  const prefectCount = prefectFlowRuns?.length ?? 0;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Orchestration"
        description="Prefect-native orchestration status, worker health, and legacy Oats run records."
      />

      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="conversation-dags">Conversation DAGs</TabsTrigger>
          <TabsTrigger value="prefect">
            Prefect {prefectCount > 0 ? `(${prefectCount})` : ""}
          </TabsTrigger>
          <TabsTrigger value="prefect-ui">Prefect UI</TabsTrigger>
        </TabsList>

        <TabsContent value="conversation-dags">
          <ConversationDagList />
        </TabsContent>

        <TabsContent value="prefect">
          <OvernightOatsPanel />
        </TabsContent>

        <TabsContent value="prefect-ui">
          <PrefectUiEmbed />
        </TabsContent>
      </Tabs>
    </div>
  );
}
