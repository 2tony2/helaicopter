"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { AuthCredential } from "@/lib/types";

export function AddCredentialDialog({
  onSubmit,
  onOauth,
  pending = false,
}: {
  onSubmit?: (input: {
    provider: AuthCredential["provider"];
    credentialType: "api_key";
    apiKey: string;
  }) => void;
  onOauth?: (provider: AuthCredential["provider"]) => void;
  pending?: boolean;
}) {
  const [provider, setProvider] = useState<AuthCredential["provider"]>("claude");
  const [apiKey, setApiKey] = useState("");

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm">Add credential</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add credential</DialogTitle>
          <DialogDescription>
            Register an API key now or start an OAuth redirect for managed auth.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="credential-provider">
              Provider
            </label>
            <select
              id="credential-provider"
              className="flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={provider}
              onChange={(event) => setProvider(event.target.value as AuthCredential["provider"])}
            >
              <option value="claude">Claude</option>
              <option value="codex">Codex</option>
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="credential-api-key">
              API key
            </label>
            <Input
              id="credential-api-key"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="sk-..."
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            disabled={pending}
            onClick={() => onOauth?.(provider)}
          >
            OAuth redirect
          </Button>
          <Button
            disabled={pending || apiKey.trim().length === 0}
            onClick={() =>
              onSubmit?.({
                provider,
                credentialType: "api_key",
                apiKey,
              })
            }
          >
            Save API key
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
