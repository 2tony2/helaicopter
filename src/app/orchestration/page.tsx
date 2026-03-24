import { OrchestrationHub } from "@/components/orchestration/orchestration-hub";
import { resolveOrchestrationInitialTab } from "@/components/orchestration/tabs";

export default function OrchestrationPage({
  searchParams,
}: {
  searchParams: { tab?: string; flowRunId?: string };
}) {
  const { tab } = searchParams;
  const initialTab = resolveOrchestrationInitialTab(tab);

  return <OrchestrationHub initialTab={initialTab} />;
}
