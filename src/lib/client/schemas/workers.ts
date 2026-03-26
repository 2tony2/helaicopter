import { z } from "zod";

const providerSchema = z.enum(["claude", "codex"]);
const workerStatusSchema = z.enum(["idle", "busy", "draining", "dead", "auth_expired"]);

export const workerCapabilitiesSchema = z.object({
  provider: providerSchema,
  models: z.array(z.string()),
  maxConcurrentTasks: z.number(),
  supportsDiscovery: z.boolean(),
  supportsResume: z.boolean(),
  tags: z.array(z.string()),
});

export const workerSchema = z.object({
  workerId: z.string(),
  workerType: z.string(),
  provider: providerSchema,
  capabilities: workerCapabilitiesSchema,
  host: z.string(),
  pid: z.number().nullable().optional(),
  worktreeRoot: z.string().nullable().optional(),
  registeredAt: z.string(),
  lastHeartbeatAt: z.string(),
  status: workerStatusSchema,
  currentTaskId: z.string().nullable().optional(),
  currentRunId: z.string().nullable().optional(),
});

export const workerListSchema = z.array(workerSchema);

export type WorkerPayload = z.infer<typeof workerSchema>;
