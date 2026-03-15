import type { Metadata } from "next";
import { DebuggingDashboard } from "@/components/debugging/debugging-dashboard";

export const metadata: Metadata = {
  title: "Debugging | Helaicopter",
  description: "Find editing-related conversations, failures, and subagent runs.",
};

export default function DebuggingPage() {
  return <DebuggingDashboard />;
}
