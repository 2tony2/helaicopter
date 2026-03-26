"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { AuthCredential } from "@/lib/types";

export function CredentialProviderActions({
  onConnectClaudeCli,
  onOauth,
  pending = false,
}: {
  onConnectClaudeCli?: () => void;
  onOauth?: (provider: AuthCredential["provider"]) => void;
  pending?: boolean;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="rounded-lg border bg-muted/30 p-4">
        <div className="text-sm font-medium">Claude</div>
        <p className="mt-1 text-sm text-muted-foreground">Reuse Claude CLI session.</p>
        <Button
          className="mt-4 w-full"
          disabled={pending}
          onClick={() => onConnectClaudeCli?.()}
        >
          Reuse Claude CLI session
        </Button>
      </div>

      <div className="rounded-lg border bg-muted/30 p-4">
        <div className="text-sm font-medium">Codex</div>
        <p className="mt-1 text-sm text-muted-foreground">OAuth redirect.</p>
        <Button className="mt-4 w-full" disabled={pending} onClick={() => onOauth?.("codex")}>
          OAuth redirect
        </Button>
      </div>
    </div>
  );
}

export function AddCredentialDialog({
  onConnectClaudeCli,
  onOauth,
  pending = false,
}: {
  onConnectClaudeCli?: () => void;
  onOauth?: (provider: AuthCredential["provider"]) => void;
  pending?: boolean;
}) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm">Add credential</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add credential</DialogTitle>
          <DialogDescription>
            Reuse your local Claude CLI session or start a Codex OAuth redirect.
          </DialogDescription>
        </DialogHeader>

        <CredentialProviderActions
          onConnectClaudeCli={onConnectClaudeCli}
          onOauth={onOauth}
          pending={pending}
        />

      </DialogContent>
    </Dialog>
  );
}
