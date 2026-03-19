export type OrchestrationTab = "conversation-dags" | "prefect" | "prefect-ui";

export const PREFECT_UI_URL = "http://127.0.0.1:4200";

export function resolveOrchestrationInitialTab(
  tab?: string
): OrchestrationTab {
  if (tab === "conversation-dags" || tab === "prefect-ui" || tab === "prefect") {
    return tab;
  }
  return "prefect";
}
