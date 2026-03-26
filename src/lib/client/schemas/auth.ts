import { z } from "zod";

const providerSchema = z.enum(["claude", "codex"]);
const credentialTypeSchema = z.enum(["oauth_token", "api_key", "local_cli_session"]);
const credentialStatusSchema = z.enum(["active", "expired", "revoked", "pending"]);

export const authCredentialSchema = z.object({
  credentialId: z.string(),
  provider: providerSchema,
  credentialType: credentialTypeSchema,
  status: credentialStatusSchema,
  providerStatusCode: z.string().nullable().optional(),
  providerStatusMessage: z.string().nullable().optional(),
  tokenExpiresAt: z.string().nullable().optional(),
  cliConfigPath: z.string().nullable().optional(),
  subscriptionId: z.string().nullable().optional(),
  subscriptionTier: z.string().nullable().optional(),
  rateLimitTier: z.string().nullable().optional(),
  createdAt: z.string(),
  lastUsedAt: z.string().nullable().optional(),
  lastRefreshedAt: z.string().nullable().optional(),
  cumulativeCostUsd: z.number(),
  costSinceReset: z.number(),
});

export const authCredentialListSchema = z.array(authCredentialSchema);

export const oauthInitiateSchema = z.object({
  redirectUrl: z.string().url(),
  state: z.string(),
});

export type AuthCredentialPayload = z.infer<typeof authCredentialSchema>;
