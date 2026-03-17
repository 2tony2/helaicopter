import { OrchestrationHub } from "@/components/orchestration/orchestration-hub";

export default async function OrchestrationPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const { tab } = await searchParams;
  const initialTab = tab === "oats" ? "oats" : "conversation-dags";

  return <OrchestrationHub initialTab={initialTab} />;
}
