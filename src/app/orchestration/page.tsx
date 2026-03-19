import { OrchestrationHub } from "@/components/orchestration/orchestration-hub";

export default async function OrchestrationPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const { tab } = await searchParams;
  const initialTab =
    tab === "conversation-dags" ? "conversation-dags" : "prefect";

  return <OrchestrationHub initialTab={initialTab} />;
}
