import { OrchestrationHub } from "@/components/orchestration/orchestration-hub";
import { resolveOrchestrationInitialTab } from "@/components/orchestration/tabs";

export default function OrchestrationPage({
  searchParams,
}: {
  searchParams: { tab?: string; flowRunId?: string; prefectPath?: string };
}) {
  const { tab, prefectPath } = searchParams;
  const initialTab = resolveOrchestrationInitialTab(tab);

  return (
    <OrchestrationHub
      initialTab={initialTab}
      prefectPath={prefectPath}
    />
  );
}
