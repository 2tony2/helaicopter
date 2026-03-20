import { PlanDetailView } from "@/views/plans/plan-detail-view";

export default function PlanDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  return <PlanDetailView params={params} />;
}
