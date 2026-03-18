import { createHash } from "crypto";
import {
  getRawConversation,
  getRawTasksForSession,
  listRawConversations,
} from "./export-backend/claude-data";
import { calculateCost } from "../src/lib/pricing";
import { startOfTodayIso } from "../src/lib/time-windows";

const MAX_WINDOW_DAYS = 365;

function stable(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(stable);
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => [key, stable(nested)])
    );
  }

  return value;
}

async function main() {
  const metaOnly = process.argv.includes("--meta-only");
  const conversations = await listRawConversations(undefined, MAX_WINDOW_DAYS, {
    dayScope: "beforeToday",
  });
  const sortedSummaries = conversations
    .map((conversation) => stable(conversation))
    .sort((left, right) =>
      JSON.stringify(left).localeCompare(JSON.stringify(right))
    );
  const inputKey = createHash("sha256")
    .update(JSON.stringify(sortedSummaries))
    .digest("hex");
  const now = Date.now();
  const cutoffStart = now - MAX_WINDOW_DAYS * 24 * 60 * 60 * 1000;
  const timestamps = conversations
    .map((conversation) => conversation.timestamp)
    .filter((timestamp) => Number.isFinite(timestamp) && timestamp > 0);
  const windowEnd = startOfTodayIso();
  const oldestConversation = timestamps.length > 0 ? Math.min(...timestamps) : cutoffStart;
  const windowStart = new Date(Math.max(cutoffStart, oldestConversation)).toISOString();

  process.stdout.write(
    `${JSON.stringify({
      type: "meta",
      exportedAt: new Date().toISOString(),
      conversationCount: conversations.length,
      inputKey,
      windowDays: MAX_WINDOW_DAYS,
      windowStart,
      windowEnd,
      scopeLabel: `Historical conversations before today from the last ${MAX_WINDOW_DAYS} days`,
    })}\n`
  );

  if (metaOnly) {
    return;
  }

  for (const summary of conversations) {
    const detail = await getRawConversation(summary.projectPath, summary.sessionId);
    const tasks = await getRawTasksForSession(summary.sessionId);
    const cost = calculateCost(
      {
        inputTokens: summary.totalInputTokens,
        outputTokens: summary.totalOutputTokens,
        cacheWriteTokens: summary.totalCacheCreationTokens,
        cacheReadTokens: summary.totalCacheReadTokens,
      },
      summary.model
    );

    process.stdout.write(
      `${JSON.stringify({
        type: "conversation",
        summary,
        detail,
        tasks,
        cost,
      })}\n`
    );
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
