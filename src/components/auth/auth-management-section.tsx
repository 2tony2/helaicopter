"use client";

import { KeyRound, RefreshCw, Wallet } from "lucide-react";

import { AddCredentialDialog } from "@/components/auth/add-credential-dialog";
import { CredentialList } from "@/components/auth/credential-list";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAddCredential,
  useCredentials,
  useInitiateOauth,
  useRefreshCredential,
  useRevokeCredential,
} from "@/lib/client/auth";
import type { AuthCredential } from "@/lib/types";

function sumCost(credentials: AuthCredential[]) {
  return credentials.reduce((total, credential) => total + credential.cumulativeCostUsd, 0);
}

export function AuthManagementSection({
  credentials,
  onRefresh,
  onRevoke,
  onAddApiKey,
  onInitiateOauth,
  pending = false,
  error,
}: {
  credentials: AuthCredential[];
  onRefresh?: (credentialId: string) => void;
  onRevoke?: (credentialId: string) => void;
  onAddApiKey?: (input: {
    provider: AuthCredential["provider"];
    credentialType: "api_key";
    apiKey: string;
  }) => void;
  onInitiateOauth?: (provider: AuthCredential["provider"]) => void;
  pending?: boolean;
  error?: string | null;
}) {
  const active = credentials.filter((credential) => credential.status === "active").length;
  const revoked = credentials.filter((credential) => credential.status === "revoked").length;

  return (
    <section id="auth-management" className="space-y-4 scroll-mt-24">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">Auth Management</h2>
          <p className="text-sm text-muted-foreground">
            Credential health, expiry, and spend tracking for local provider access.
          </p>
        </div>
        <AddCredentialDialog
          onSubmit={onAddApiKey}
          onOauth={onInitiateOauth}
          pending={pending}
        />
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Credentials
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <KeyRound className="h-5 w-5 text-sky-500" />
              {credentials.length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Active</div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <RefreshCw className="h-5 w-5 text-emerald-500" />
              {active}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">{revoked} revoked</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              Cumulative cost
            </div>
            <div className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <Wallet className="h-5 w-5 text-violet-500" />
              ${sumCost(credentials).toFixed(2)}
            </div>
          </CardContent>
        </Card>
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-400/40 bg-rose-500/5 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      ) : null}

      <CredentialList
        credentials={credentials}
        onRefresh={onRefresh}
        onRevoke={onRevoke}
      />
    </section>
  );
}

export function AuthManagementPanel() {
  const { data: credentials, isLoading } = useCredentials();
  const addCredential = useAddCredential();
  const revokeCredential = useRevokeCredential();
  const refreshCredential = useRefreshCredential();
  const oauth = useInitiateOauth();

  if (isLoading && !(credentials && credentials.length > 0)) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 2 }).map((_, index) => (
          <Skeleton key={index} className="h-32 w-full" />
        ))}
      </div>
    );
  }

  return (
    <AuthManagementSection
      credentials={credentials ?? []}
      onRefresh={(credentialId) => void refreshCredential.run(credentialId)}
      onRevoke={(credentialId) => void revokeCredential.run(credentialId)}
      onAddApiKey={(input) => void addCredential.run(input)}
      onInitiateOauth={(provider) => {
        void oauth.run(provider).then((result) => {
          if (
            typeof window !== "undefined" &&
            result &&
            typeof result === "object" &&
            "redirectUrl" in result &&
            typeof result.redirectUrl === "string"
          ) {
            window.location.assign(result.redirectUrl);
          }
        });
      }}
      pending={
        addCredential.isMutating ||
        revokeCredential.isMutating ||
        refreshCredential.isMutating ||
        oauth.isMutating
      }
      error={
        addCredential.error ??
        revokeCredential.error ??
        refreshCredential.error ??
        oauth.error
      }
    />
  );
}

export { AddCredentialDialog };
