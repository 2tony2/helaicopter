import { redirect } from "next/navigation";

export default function DagsPage() {
  redirect("/orchestration?tab=conversation-dags");
}
