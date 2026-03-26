import { OrchestrationHub } from "@/components/orchestration/orchestration-hub";
import { resolveOrchestrationInitialTab } from "@/components/orchestration/tabs";

export default async function OrchestrationPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string; flowRunId?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const { tab } = resolvedSearchParams;
  const initialTab = resolveOrchestrationInitialTab(tab);

  return <OrchestrationHub initialTab={initialTab} />;
}
