import type { ConversationSummary } from "@/lib/types";

export type DebugScenarioId =
  | "editing"
  | "frontend"
  | "backend"
  | "tests"
  | "tool-failures"
  | "multi-agent";

export interface DebugScenarioDefinition {
  id: DebugScenarioId;
  label: string;
  description: string;
  keywords: string[];
  toolNames: string[];
}

export interface DebugScenarioMatch {
  id: DebugScenarioId;
  label: string;
  score: number;
  reasons: string[];
}

export interface DebugConversationMatch {
  conversation: ConversationSummary;
  searchText: string;
  score: number;
  matches: DebugScenarioMatch[];
  reasons: string[];
}

export interface DebugConversationFilters {
  provider?: "all" | "claude" | "codex";
  threadType?: "all" | "main" | "subagent";
  search?: string;
  selectedScenarioIds?: DebugScenarioId[];
}

export const DEBUG_SCENARIOS: DebugScenarioDefinition[] = [
  {
    id: "editing",
    label: "Editing",
    description: "File edits, patches, refactors, and implementation work.",
    keywords: ["edit", "patch", "refactor", "implement", "feature", "rename", "fix", "bug"],
    toolNames: ["edit", "multiedit", "write", "apply_patch", "str_replace_editor"],
  },
  {
    id: "frontend",
    label: "Frontend",
    description: "UI, styling, React, Next.js, and component changes.",
    keywords: ["ui", "react", "next", "component", "css", "tailwind", "frontend", "layout"],
    toolNames: ["edit", "multiedit", "write", "apply_patch"],
  },
  {
    id: "backend",
    label: "Backend",
    description: "API, routes, data, migrations, and schema work.",
    keywords: ["api", "route", "server", "backend", "database", "sql", "migration", "schema"],
    toolNames: ["edit", "multiedit", "write", "apply_patch", "bash", "exec_command"],
  },
  {
    id: "tests",
    label: "Tests",
    description: "Testing, linting, builds, and type-checking workflows.",
    keywords: ["test", "tests", "vitest", "jest", "playwright", "lint", "typecheck", "build"],
    toolNames: ["bash", "exec_command"],
  },
  {
    id: "tool-failures",
    label: "Tool Failures",
    description: "Conversations with failed tool calls worth auditing.",
    keywords: [],
    toolNames: [],
  },
  {
    id: "multi-agent",
    label: "Subagents",
    description: "Runs involving spawned agents or subagent threads.",
    keywords: [],
    toolNames: ["task", "spawn_agent"],
  },
];

function normalizeText(value: string | undefined): string {
  return (value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function normalizeToolName(toolName: string): string {
  return toolName.toLowerCase().replace(/\s+/g, "_");
}

function getProvider(conversation: ConversationSummary): "claude" | "codex" {
  return conversation.projectPath.startsWith("codex:") ? "codex" : "claude";
}

function buildSearchText(conversation: ConversationSummary): string {
  return normalizeText(
    [
      conversation.firstMessage,
      conversation.projectName,
      conversation.projectPath,
      conversation.gitBranch,
      conversation.model,
      conversation.reasoningEffort,
      conversation.speed,
      conversation.threadType,
      ...Object.keys(conversation.toolBreakdown),
    ].join(" ")
  );
}

function matchScenario(
  conversation: ConversationSummary,
  searchText: string,
  scenario: DebugScenarioDefinition
): DebugScenarioMatch | null {
  const toolHits = Object.entries(conversation.toolBreakdown)
    .filter(([toolName]) => scenario.toolNames.includes(normalizeToolName(toolName)))
    .sort((a, b) => b[1] - a[1]);
  const keywordHits = scenario.keywords.filter((keyword) =>
    searchText.includes(normalizeText(keyword))
  );
  const reasons: string[] = [];
  let score = 0;

  if (toolHits.length > 0) {
    const toolSummary = toolHits
      .slice(0, 3)
      .map(([toolName, count]) => `${toolName} x${count}`)
      .join(", ");
    reasons.push(`tools ${toolSummary}`);
    score += toolHits.reduce((total, [, count]) => total + count, 0) * 3;
  }

  if (keywordHits.length > 0) {
    const terms = keywordHits.slice(0, 4).join(", ");
    reasons.push(`mentions ${terms}`);
    score += keywordHits.length * 4;
  }

  if (scenario.id === "tool-failures" && conversation.failedToolCallCount > 0) {
    reasons.push(`${conversation.failedToolCallCount} failed tool call${conversation.failedToolCallCount === 1 ? "" : "s"}`);
    score += conversation.failedToolCallCount * 5;
  }

  if (scenario.id === "multi-agent") {
    if (conversation.threadType === "subagent") {
      reasons.push("subagent thread");
      score += 8;
    }
    if (conversation.subagentCount > 0) {
      reasons.push(`${conversation.subagentCount} spawned subagent${conversation.subagentCount === 1 ? "" : "s"}`);
      score += conversation.subagentCount * 4;
    }
  }

  if (score <= 0) {
    return null;
  }

  return {
    id: scenario.id,
    label: scenario.label,
    score,
    reasons: unique(reasons),
  };
}

function matchesSearch(searchText: string, search: string | undefined): boolean {
  const terms = normalizeText(search).split(" ").filter(Boolean);
  if (terms.length === 0) {
    return true;
  }
  return terms.every((term) => searchText.includes(term));
}

export function buildDebugConversationMatches(
  conversations: ConversationSummary[]
): DebugConversationMatch[] {
  return conversations
    .map((conversation) => {
      const searchText = buildSearchText(conversation);
      const matches = DEBUG_SCENARIOS.map((scenario) =>
        matchScenario(conversation, searchText, scenario)
      ).filter((match): match is DebugScenarioMatch => match !== null);
      const score = matches.reduce((total, match) => total + match.score, 0);

      return {
        conversation,
        searchText,
        score,
        matches,
        reasons: unique(matches.flatMap((match) => match.reasons)).slice(0, 6),
      };
    })
    .filter((row) => row.matches.length > 0)
    .sort((a, b) => {
      if (b.score !== a.score) {
        return b.score - a.score;
      }
      return b.conversation.timestamp - a.conversation.timestamp;
    });
}

export function filterDebugConversationMatches(
  matches: DebugConversationMatch[],
  filters: DebugConversationFilters = {}
): DebugConversationMatch[] {
  const selectedScenarioIds = filters.selectedScenarioIds ?? [];

  return matches.filter((row) => {
    const provider = getProvider(row.conversation);
    if (filters.provider && filters.provider !== "all" && provider !== filters.provider) {
      return false;
    }

    if (
      filters.threadType &&
      filters.threadType !== "all" &&
      row.conversation.threadType !== filters.threadType
    ) {
      return false;
    }

    if (!matchesSearch(row.searchText, filters.search)) {
      return false;
    }

    if (selectedScenarioIds.length === 0) {
      return true;
    }

    return row.matches.some((match) => selectedScenarioIds.includes(match.id));
  });
}

export function countMatchesByScenario(
  matches: DebugConversationMatch[]
): Record<DebugScenarioId, number> {
  const counts = Object.fromEntries(
    DEBUG_SCENARIOS.map((scenario) => [scenario.id, 0])
  ) as Record<DebugScenarioId, number>;

  for (const row of matches) {
    for (const match of row.matches) {
      counts[match.id] += 1;
    }
  }

  return counts;
}
