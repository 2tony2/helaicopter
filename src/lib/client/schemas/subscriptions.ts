import { z } from "zod";

import {
  isoDateString,
  providerSchema,
} from "./shared.ts";

const providerSubscriptionSnakeSchema = z.object({
  provider: providerSchema,
  has_subscription: z.boolean(),
  monthly_cost: z.number().finite(),
  updated_at: isoDateString,
});

const providerSubscriptionCamelSchema = z.object({
  provider: providerSchema,
  hasSubscription: z.boolean(),
  monthlyCost: z.number().finite(),
  updatedAt: isoDateString,
});

export const providerSubscriptionSchema = z.union([
  providerSubscriptionSnakeSchema,
  providerSubscriptionCamelSchema,
]);

export const subscriptionSettingsSchema = z.object({
  claude: providerSubscriptionSchema,
  codex: providerSubscriptionSchema,
});

export const subscriptionSettingsWriteSchema = z.object({
  claude: providerSubscriptionCamelSchema,
  codex: providerSubscriptionCamelSchema,
});

export type SubscriptionSettingsPayload = z.infer<typeof subscriptionSettingsSchema>;
