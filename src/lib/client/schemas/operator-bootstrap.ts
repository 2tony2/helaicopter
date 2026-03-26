import { z } from "zod";

const providerSchema = z.enum(["claude", "codex"]);
const severitySchema = z.enum(["error", "warning", "info"]);
const overallStatusSchema = z.enum(["ready", "blocked"]);
const providerReadinessStatusSchema = z.enum(["ready", "degraded", "blocked", "unknown"]);

export const bootstrapReasonSchema = z.object({
  code: z.string(),
  severity: severitySchema,
  message: z.string(),
  nextStep: z.string().nullable().optional(),
});

export const providerBootstrapSummarySchema = z.object({
  provider: providerSchema,
  status: providerReadinessStatusSchema,
  workerCount: z.number(),
  credentialCount: z.number(),
  blockingReasons: z.array(bootstrapReasonSchema),
});

export const operatorBootstrapSchema = z.object({
  overallStatus: overallStatusSchema,
  resolverRunning: z.boolean(),
  blockingReasons: z.array(bootstrapReasonSchema),
  providers: z.array(providerBootstrapSummarySchema),
  totalWorkerCount: z.number(),
  totalCredentialCount: z.number(),
  hasClaudeWorker: z.boolean(),
  hasCodexWorker: z.boolean(),
});

export type OperatorBootstrapPayload = z.infer<typeof operatorBootstrapSchema>;
