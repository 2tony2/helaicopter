import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { AuthCredential } from "@/lib/types";

function formatMoney(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

export function CredentialList({
  credentials,
  onRefresh,
  onRevoke,
  pendingCredentialId,
}: {
  credentials: AuthCredential[];
  onRefresh?: (credentialId: string) => void;
  onRevoke?: (credentialId: string) => void;
  pendingCredentialId?: string | null;
}) {
  return (
    <div className="grid gap-3 xl:grid-cols-2">
      {credentials.map((credential) => {
        const isPending = pendingCredentialId === credential.credentialId;
        return (
          <Card key={credential.credentialId}>
            <CardContent className="space-y-4 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="font-medium">{credential.credentialId}</div>
                  <div className="text-sm text-muted-foreground">
                    {credential.provider} {credential.credentialType}
                  </div>
                </div>
                <Badge variant="outline">{credential.status}</Badge>
              </div>

              <div className="grid gap-2 text-sm md:grid-cols-2">
                <div>
                  <div className="font-medium">Expiry</div>
                  <div className="text-muted-foreground">
                    {credential.tokenExpiresAt ?? "no managed expiry"}
                  </div>
                </div>
                <div>
                  <div className="font-medium">Cumulative cost</div>
                  <div className="text-muted-foreground">
                    {formatMoney(credential.cumulativeCostUsd)}
                  </div>
                </div>
                <div>
                  <div className="font-medium">Last used</div>
                  <div className="text-muted-foreground">
                    {credential.lastUsedAt ?? "never"}
                  </div>
                </div>
                <div>
                  <div className="font-medium">Subscription</div>
                  <div className="text-muted-foreground">
                    {credential.subscriptionTier ?? credential.rateLimitTier ?? "none"}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isPending}
                  onClick={() => onRefresh?.(credential.credentialId)}
                >
                  Refresh auth
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isPending}
                  onClick={() => onRevoke?.(credential.credentialId)}
                >
                  Revoke
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
