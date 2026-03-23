"use client";

import type { ReactNode } from "react";
import type { JsonObject, JsonValue, OpenClawProviderDetail } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function formatValue(value: JsonValue | undefined): string {
  if (value === undefined) return "unknown";
  if (value === null) return "null";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return `${value.length} items`;
  return `${Object.keys(value).length} fields`;
}

function objectEntries(value: JsonObject | undefined): Array<[string, JsonValue | undefined]> {
  if (!value) {
    return [];
  }
  return Object.entries(value).sort(([left], [right]) => left.localeCompare(right));
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

function KeyValueGrid({
  entries,
}: {
  entries: Array<[string, JsonValue | undefined]>;
}) {
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No structured fields captured.</p>;
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-md border bg-muted/30 p-3">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">{key}</div>
          <div className="mt-1 break-words text-sm">{formatValue(value)}</div>
        </div>
      ))}
    </div>
  );
}

function JsonPreview({
  value,
  label = "Raw",
}: {
  value: JsonValue | undefined;
  label?: string;
}) {
  if (value === undefined) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <pre className="overflow-x-auto rounded-md border bg-muted/40 p-3 text-xs leading-5">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function ArtifactInventorySection({ detail }: { detail: OpenClawProviderDetail }) {
  return (
    <Section
      title="Artifact Inventory"
      subtitle="Live transcript identity plus attached OpenClaw archive siblings."
    >
      <KeyValueGrid entries={objectEntries(detail.artifactInventory.liveTranscript)} />
      <div className="space-y-2">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">Attached Archives</div>
        {detail.artifactInventory.attachedArchives.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2">
            {detail.artifactInventory.attachedArchives.map((archive, index) => (
              <div key={`${archive.path ?? archive.kind ?? "archive"}:${index}`} className="rounded-md border p-3">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{archive.kind ?? "archive"}</Badge>
                  {archive.status ? <Badge variant="outline">{archive.status}</Badge> : null}
                </div>
                <div className="mt-2 text-sm break-all">{archive.path ?? "unknown path"}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No attached archives were discovered.</p>
        )}
      </div>
      <JsonPreview value={detail.artifactInventory} label="Raw Inventory" />
    </Section>
  );
}

export function OpenClawTab({ detail }: { detail: OpenClawProviderDetail }) {
  const overviewEntries: Array<[string, JsonValue | undefined]> = [
    ["sessionKey", detail.sessionStore?.sessionKey],
    ["sessionId", detail.sessionStore?.sessionId],
    ["origin", detail.sessionStore?.origin],
    ["deliveryContext", detail.sessionStore?.deliveryContext],
    ["workspaceDir", detail.systemPrompt?.workspaceDir],
    ["transcriptTotalTokens", detail.usageReconciliation?.transcriptTotalTokens],
    ["storeTotalTokens", detail.usageReconciliation?.storeTotalTokens],
    ["memoryPath", detail.memoryStore?.path],
  ];

  return (
    <div className="mt-4 space-y-6">
      <Section
        title="Session Overview"
        subtitle="OpenClaw-specific session metadata stitched from transcripts, sessions.json, and memory metadata."
      >
        <KeyValueGrid entries={overviewEntries} />
      </Section>

      <Section title="Routing And Origin" subtitle="Session-store routing, origin, and delivery metadata.">
        <KeyValueGrid entries={objectEntries(detail.sessionStore)} />
        <JsonPreview value={detail.sessionStore} label="Raw Session Store" />
      </Section>

      <Section title="Skills And Prompt Bootstrap" subtitle="Resolved skills and the system prompt bootstrap snapshot.">
        <KeyValueGrid entries={objectEntries(detail.skills)} />
        <JsonPreview value={detail.skills} label="Raw Skills" />
      </Section>

      <Section title="System Prompt" subtitle="Workspace injection and prompt bootstrap state from OpenClaw.">
        <KeyValueGrid entries={objectEntries(detail.systemPrompt)} />
        <JsonPreview value={detail.systemPrompt} label="Raw System Prompt" />
      </Section>

      <Section title="Usage Reconciliation" subtitle="Transcript totals reconciled against the mutable OpenClaw session store counters.">
        <KeyValueGrid entries={objectEntries(detail.usageReconciliation)} />
        <JsonPreview value={detail.usageReconciliation} label="Raw Usage Reconciliation" />
      </Section>

      <Section title="Transcript Diagnostics" subtitle="Parsed event matrix coverage, compaction markers, branch summaries, and unmatched events.">
        <KeyValueGrid entries={objectEntries(detail.transcriptDiagnostics)} />
        <JsonPreview value={detail.transcriptDiagnostics} label="Raw Diagnostics" />
      </Section>

      <Section title="Memory Store" subtitle="Detail-only summary of OpenClaw memory/main.sqlite without loading embeddings or chunk bodies.">
        <KeyValueGrid entries={objectEntries(detail.memoryStore)} />
        <JsonPreview value={detail.memoryStore} label="Raw Memory Store" />
      </Section>

      <ArtifactInventorySection detail={detail} />

      <Section title="Raw Payloads" subtitle="Preserved raw OpenClaw payloads for provenance and debugging.">
        <JsonPreview value={detail.raw} />
      </Section>
    </div>
  );
}
