import { z } from "zod";

import { isoDateString } from "./shared.ts";

const trimmedString = z.string().trim();
const nullableTrimmedString = z.union([trimmedString, z.null()]);
const nullableFiniteNumber = z.union([z.number().finite(), z.null()]);
const databaseStatusKeySchema = z.enum([
  "frontend_cache",
  "sqlite",
  "duckdb",
]);
const databaseRoleSchema = z.enum([
  "cache",
  "metadata",
  "inspection",
  "orchestration",
]);
const databaseAvailabilitySchema = z.enum([
  "ready",
  "missing",
  "unreachable",
]);

const databaseLoadMetricSnakeSchema = z.object({
  label: trimmedString,
  value: nullableFiniteNumber.optional(),
  display_value: nullableTrimmedString.optional(),
});

const databaseLoadMetricCamelSchema = z.object({
  label: trimmedString,
  value: nullableFiniteNumber.optional(),
  displayValue: nullableTrimmedString.optional(),
});

const databaseLoadMetricSchema = z.union([
  databaseLoadMetricSnakeSchema,
  databaseLoadMetricCamelSchema,
]);

const databaseColumnSnakeSchema = z.object({
  name: trimmedString,
  type: trimmedString,
  nullable: z.boolean(),
  default_value: nullableTrimmedString.optional(),
  is_primary_key: z.boolean(),
  references: nullableTrimmedString.optional(),
});

const databaseColumnCamelSchema = z.object({
  name: trimmedString,
  type: trimmedString,
  nullable: z.boolean(),
  defaultValue: nullableTrimmedString.optional(),
  isPrimaryKey: z.boolean(),
  references: nullableTrimmedString.optional(),
});

const databaseColumnSchema = z.union([
  databaseColumnSnakeSchema,
  databaseColumnCamelSchema,
]);

const databaseTableSnakeSchema = z.object({
  name: trimmedString,
  row_count: z.number().finite(),
  size_bytes: nullableFiniteNumber.optional(),
  size_display: nullableTrimmedString.optional(),
  columns: z.array(databaseColumnSchema),
  serving_class: trimmedString.optional(),
  integration_type: trimmedString.optional(),
  fastapi_routes: z.array(trimmedString).optional(),
  sqlalchemy_model: nullableTrimmedString.optional(),
  note: nullableTrimmedString.optional(),
});

const databaseTableCamelSchema = z.object({
  name: trimmedString,
  rowCount: z.number().finite(),
  sizeBytes: nullableFiniteNumber.optional(),
  sizeDisplay: nullableTrimmedString.optional(),
  columns: z.array(databaseColumnSchema),
  servingClass: trimmedString.optional(),
  integrationType: trimmedString.optional(),
  fastapiRoutes: z.array(trimmedString).optional(),
  sqlalchemyModel: nullableTrimmedString.optional(),
  note: nullableTrimmedString.optional(),
});

const databaseTableSchema = z.union([
  databaseTableSnakeSchema,
  databaseTableCamelSchema,
]);

const databaseArtifactSnakeSchema = z.object({
  key: databaseStatusKeySchema,
  label: trimmedString,
  engine: trimmedString,
  role: databaseRoleSchema,
  availability: databaseAvailabilitySchema,
  health: nullableTrimmedString.optional(),
  operational_status: nullableTrimmedString.optional(),
  note: nullableTrimmedString.optional(),
  error: nullableTrimmedString.optional(),
  path: nullableTrimmedString.optional(),
  target: nullableTrimmedString.optional(),
  public_path: nullableTrimmedString.optional(),
  docs_url: nullableTrimmedString.optional(),
  table_count: z.number().finite(),
  size_bytes: nullableFiniteNumber.optional(),
  size_display: nullableTrimmedString.optional(),
  inventory_summary: nullableTrimmedString.optional(),
  load: z.array(databaseLoadMetricSchema),
  tables: z.array(databaseTableSchema),
});

const databaseArtifactCamelSchema = z.object({
  key: databaseStatusKeySchema,
  label: trimmedString,
  engine: trimmedString,
  role: databaseRoleSchema,
  availability: databaseAvailabilitySchema,
  health: nullableTrimmedString.optional(),
  operationalStatus: nullableTrimmedString.optional(),
  note: nullableTrimmedString.optional(),
  error: nullableTrimmedString.optional(),
  path: nullableTrimmedString.optional(),
  target: nullableTrimmedString.optional(),
  publicPath: nullableTrimmedString.optional(),
  docsUrl: nullableTrimmedString.optional(),
  tableCount: z.number().finite(),
  sizeBytes: nullableFiniteNumber.optional(),
  sizeDisplay: nullableTrimmedString.optional(),
  inventorySummary: nullableTrimmedString.optional(),
  load: z.array(databaseLoadMetricSchema),
  tables: z.array(databaseTableSchema),
});

const databaseArtifactSchema = z.union([
  databaseArtifactSnakeSchema,
  databaseArtifactCamelSchema,
]);

const databaseRuntimeSnakeSchema = z.object({
  analytics_read_backend: z.literal("legacy"),
  conversation_summary_read_backend: z.literal("legacy"),
});

const databaseRuntimeCamelSchema = z.object({
  analyticsReadBackend: z.literal("legacy"),
  conversationSummaryReadBackend: z.literal("legacy"),
});

const databaseRuntimeSchema = z.union([
  databaseRuntimeSnakeSchema,
  databaseRuntimeCamelSchema,
]);

const databaseCollectionSchema = z.object({
  frontendCache: databaseArtifactSchema.optional(),
  frontend_cache: databaseArtifactSchema.optional(),
  sqlite: databaseArtifactSchema.optional(),
  duckdb: databaseArtifactSchema.optional(),
  legacyDuckdb: databaseArtifactSchema.optional(),
  legacy_duckdb: databaseArtifactSchema.optional(),
}).superRefine((value, ctx) => {
  if (!value.frontendCache && !value.frontend_cache) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["frontendCache"],
      message: "Expected frontendCache or frontend_cache.",
    });
  }

  if (!value.sqlite) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["sqlite"],
      message: "Expected sqlite.",
    });
  }

});

export const databaseStatusSchema = z.object({
  status: z.enum(["idle", "running", "completed", "failed"]),
  trigger: trimmedString.optional(),
  startedAt: z.union([isoDateString, z.null()]).optional(),
  started_at: z.union([isoDateString, z.null()]).optional(),
  finishedAt: z.union([isoDateString, z.null()]).optional(),
  finished_at: z.union([isoDateString, z.null()]).optional(),
  durationMs: nullableFiniteNumber.optional(),
  duration_ms: nullableFiniteNumber.optional(),
  error: nullableTrimmedString.optional(),
  lastSuccessfulRefreshAt: z.union([isoDateString, z.null()]).optional(),
  last_successful_refresh_at: z.union([isoDateString, z.null()]).optional(),
  idempotencyKey: nullableTrimmedString.optional(),
  idempotency_key: nullableTrimmedString.optional(),
  scopeLabel: trimmedString.optional(),
  scope_label: trimmedString.optional(),
  windowDays: z.number().finite().optional(),
  window_days: z.number().finite().optional(),
  windowStart: z.union([isoDateString, z.null()]).optional(),
  window_start: z.union([isoDateString, z.null()]).optional(),
  windowEnd: z.union([isoDateString, z.null()]).optional(),
  window_end: z.union([isoDateString, z.null()]).optional(),
  sourceConversationCount: z.number().finite().optional(),
  source_conversation_count: z.number().finite().optional(),
  refreshIntervalMinutes: z.number().finite().optional(),
  refresh_interval_minutes: z.number().finite().optional(),
  runtime: databaseRuntimeSchema,
  databases: databaseCollectionSchema,
}).superRefine((value, ctx) => {
  if (value.refreshIntervalMinutes === undefined && value.refresh_interval_minutes === undefined) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["refreshIntervalMinutes"],
      message: "Expected refreshIntervalMinutes or refresh_interval_minutes.",
    });
  }
});

export type DatabaseStatusPayload = z.infer<typeof databaseStatusSchema>;
export type DatabaseArtifactPayload =
  DatabaseStatusPayload["databases"][keyof DatabaseStatusPayload["databases"]];
