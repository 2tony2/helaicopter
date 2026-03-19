import { OrchestrationHub } from "@/components/orchestration/orchestration-hub";
import { resolveOrchestrationInitialTab } from "@/components/orchestration/tabs";

export default async function OrchestrationPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string; flowRunId?: string; prefectPath?: string }>;
}) {
  const { tab, flowRunId, prefectPath } = await searchParams;
  const initialTab = resolveOrchestrationInitialTab(tab);

  return (
    <OrchestrationHub
      initialTab={initialTab}
      initialFlowRunId={flowRunId}
      prefectPath={prefectPath}
    />
  );
}
