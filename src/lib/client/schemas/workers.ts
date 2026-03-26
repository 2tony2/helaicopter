import { z } from "zod";

import { bootstrapReasonSchema } from "./operator-bootstrap.ts";

const providerSchema = z.enum(["claude", "codex"]);
const workerStatusSchema = z.enum(["idle", "busy", "draining", "dead", "auth_expired"]);
const workerSessionStatusSchema = z.enum([
  "absent",
  "starting",
  "ready",
  "degraded",
  "stale",
  "failed",
  "resetting",
]);

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
  readinessReason: z.string().nullable().optional(),
  currentTaskId: z.string().nullable().optional(),
  currentRunId: z.string().nullable().optional(),
  providerSessionId: z.string().nullable().optional(),
  sessionStatus: workerSessionStatusSchema.default("absent"),
  sessionStartedAt: z.string().nullable().optional(),
  sessionLastUsedAt: z.string().nullable().optional(),
  sessionFailureReason: z.string().nullable().optional(),
  sessionResetAvailable: z.boolean().default(true),
  sessionResetRequestedAt: z.string().nullable().optional(),
});

export const workerListSchema = z.array(workerSchema);

export const workerProviderReadinessSchema = z.object({
  provider: providerSchema,
  status: z.enum(["ready", "degraded", "blocked", "unknown"]),
  healthyWorkerCount: z.number(),
  readyWorkerCount: z.number(),
  activeCredentialCount: z.number(),
  blockingReasons: z.array(bootstrapReasonSchema),
});

export const workerProviderReadinessListSchema = z.array(workerProviderReadinessSchema);

export type WorkerPayload = z.infer<typeof workerSchema>;
