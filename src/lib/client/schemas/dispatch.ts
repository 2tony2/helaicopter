import { z } from "zod";

const providerSchema = z.enum(["claude", "codex"]);

export const dispatchQueueEntrySchema = z.object({
  runId: z.string(),
  taskId: z.string(),
  provider: providerSchema,
  model: z.string(),
});

export const deferredDispatchQueueEntrySchema = dispatchQueueEntrySchema.extend({
  reason: z.string(),
  reasonLabel: z.string(),
  canRetry: z.boolean().optional().default(false),
});

export const dispatchQueueSnapshotSchema = z.object({
  ready: z.array(dispatchQueueEntrySchema),
  deferred: z.array(deferredDispatchQueueEntrySchema),
});

export const dispatchHistoryEntrySchema = z.object({
  runId: z.string(),
  taskId: z.string(),
  workerId: z.string(),
  provider: providerSchema,
  model: z.string(),
  dispatchedAt: z.string(),
});

export const dispatchHistorySchema = z.object({
  entries: z.array(dispatchHistoryEntrySchema),
});

export type DispatchQueueSnapshotPayload = z.infer<typeof dispatchQueueSnapshotSchema>;
