export type OrchestrationTab = "conversation-dags" | "orchestration";

export function resolveOrchestrationInitialTab(value?: string): OrchestrationTab {
  if (value === "conversation-dags") {
    return "conversation-dags";
  }

  return "orchestration";
}
