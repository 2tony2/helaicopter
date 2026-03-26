"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";

import type { AuthCredential } from "@/lib/types";
import * as endpoints from "@/lib/client/endpoints";
import { del, post, requestJson } from "@/lib/client/fetcher";
import {
  normalizeAuthCredential,
  normalizeAuthCredentials,
} from "@/lib/client/normalize";
import { authCredentialListSchema, authCredentialSchema } from "@/lib/client/schemas/auth";

const authSwrOptions = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  refreshInterval: 10_000,
};

export function useCredentials() {
  return useSWR<AuthCredential[]>(
    endpoints.authCredentials(),
    (url: string) =>
      requestJson(url, undefined, authCredentialListSchema, normalizeAuthCredentials),
    authSwrOptions
  );
}

function useCredentialMutation<TArgs extends unknown[]>(
  action: (...args: TArgs) => Promise<unknown>
) {
  const { mutate } = useSWRConfig();
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(...args: TArgs) {
    setIsMutating(true);
    setError(null);
    try {
      const result = await action(...args);
      await mutate((key) => typeof key === "string" && key.includes("/auth/credentials"));
      return result;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Credential action failed.");
      throw cause;
    } finally {
      setIsMutating(false);
    }
  }

  return { run, isMutating, error };
}

export function useConnectClaudeCli() {
  return useCredentialMutation(() =>
    post(
      endpoints.authCredentialClaudeCliConnect(),
      undefined,
      authCredentialSchema,
      normalizeAuthCredential
    )
  );
}

export function useConnectCodexCli() {
  return useCredentialMutation(() =>
    post(
      endpoints.authCredentialCodexCliConnect(),
      undefined,
      authCredentialSchema,
      normalizeAuthCredential
    )
  );
}

export function useRevokeCredential() {
  return useCredentialMutation((credentialId: string) =>
    del(endpoints.authCredential(credentialId))
  );
}

export function useRefreshCredential() {
  return useCredentialMutation((credentialId: string) =>
    post(
      endpoints.authCredentialRefresh(credentialId),
      undefined,
      authCredentialSchema,
      normalizeAuthCredential
    )
  );
}
