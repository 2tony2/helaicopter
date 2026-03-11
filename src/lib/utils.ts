import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getModelBadgeClasses(model: string): string {
  const m = model.toLowerCase();
  if (m.includes("claude") || m.includes("opus") || m.includes("sonnet") || m.includes("haiku")) {
    return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
  }
  if (m.includes("gpt") || m.includes("o3") || m.includes("o4")) {
    return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400";
  }
  return "";
}

export function formatModelName(model: string): string {
  return model.replace("claude-", "");
}

export function isOpenAIModel(model?: string): boolean {
  if (!model) return false;
  const m = model.toLowerCase();
  return m.includes("gpt") || m.includes("o3") || m.includes("o4");
}
