import { OrchestrationHub } from "@/components/orchestration/orchestration-hub";
import { resolveOrchestrationInitialTab } from "@/components/orchestration/tabs";

export default async function OrchestrationPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const { tab } = await searchParams;
  const initialTab = resolveOrchestrationInitialTab(tab);

  return <OrchestrationHub initialTab={initialTab} />;
}
