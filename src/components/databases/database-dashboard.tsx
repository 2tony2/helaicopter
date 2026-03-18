"use client";

import { formatDistanceToNowStrict } from "date-fns";
import { useState } from "react";
import { Database, RefreshCw, TriangleAlert } from "lucide-react";
import { useDatabaseStatus } from "@/hooks/use-conversations";
import { refreshDatabase } from "@/lib/client/mutations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { LegacyDuckDbPreview } from "@/components/databases/olap-wasm-preview";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  DatabaseAvailability,
  DatabaseArtifactStatus,
  DatabaseColumnSchema,
} from "@/lib/types";

function formatTime(value?: string | null): string {
  if (!value) return "Not refreshed yet";
  const date = new Date(value);
  return `${date.toLocaleString()} (${formatDistanceToNowStrict(date, { addSuffix: true })})`;
}

function availabilityVariant(
  availability: DatabaseAvailability
): "secondary" | "outline" | "destructive" {
  if (availability === "ready") return "secondary";
  if (availability === "missing") return "outline";
  return "destructive";
}

function ColumnChip({ column }: Readonly<{ column: DatabaseColumnSchema }>) {
  return (
    <div className="rounded-lg border bg-background/70 p-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono text-xs">{column.name}</span>
        <Badge variant="outline" className="text-[10px]">
          {column.type}
        </Badge>
        {column.isPrimaryKey && (
          <Badge variant="secondary" className="text-[10px]">
            PK
          </Badge>
        )}
        {!column.nullable && (
          <Badge variant="secondary" className="text-[10px]">
            NOT NULL
          </Badge>
        )}
      </div>
      {(column.defaultValue || column.references) && (
        <div className="mt-2 space-y-1 text-xs text-muted-foreground">
          {column.defaultValue && <div>Default: {column.defaultValue}</div>}
          {column.references && <div>Ref: {column.references}</div>}
        </div>
      )}
    </div>
  );
}

function DatabaseExplorer({
  database,
}: Readonly<{
  database: DatabaseArtifactStatus;
}>) {
  const hasSchemaDocs = Boolean(database.docsUrl);
  const location = database.target ?? database.path;

  return (
    <div className={`grid gap-6 ${hasSchemaDocs ? "xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1.35fr)]" : ""}`}>
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3 flex-wrap">
            <CardTitle className="text-base">Table Explorer</CardTitle>
            <Badge variant={availabilityVariant(database.availability)}>
              {database.availability}
            </Badge>
          </div>
          <CardDescription>
            Live schema introspection for {database.engine}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 max-h-[720px] overflow-y-auto pr-2">
          {database.note && (
            <div className="rounded-lg border bg-muted/30 p-3 text-sm text-muted-foreground">
              {database.note}
            </div>
          )}
          {location && (
            <div className="font-mono text-xs text-muted-foreground break-all">{location}</div>
          )}
          {database.error && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
              {database.error}
            </div>
          )}
          {database.tables.length === 0 && !database.error && (
            <div className="rounded-lg border bg-muted/20 p-6 text-sm text-muted-foreground">
              No tables available.
            </div>
          )}
          {database.tables.map((table) => (
            <div key={table.name} className="rounded-xl border p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium">{table.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {table.columns.length} columns
                  </div>
                </div>
                <Badge variant="outline">{table.rowCount.toLocaleString()} rows</Badge>
              </div>
              <div className="mt-3 grid gap-3">
                {table.columns.map((column) => (
                  <ColumnChip key={`${table.name}:${column.name}`} column={column} />
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {hasSchemaDocs && database.docsUrl && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">SchemaSpy</CardTitle>
            <CardDescription>
              Live HTML docs generated from the current database artifact.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {database.publicPath && (
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="font-mono text-xs text-muted-foreground break-all">
                  {database.publicPath}
                </div>
                <a
                  href={database.docsUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm underline underline-offset-4"
                >
                  Open full docs
                </a>
              </div>
            )}
            <iframe
              key={database.docsUrl}
              src={database.docsUrl}
              title={`${database.label} schema`}
              className="h-[680px] w-full rounded-xl border bg-background"
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function DatabaseDashboard() {
  const { data, isLoading, mutate } = useDatabaseStatus();
  const [isRefreshing, setIsRefreshing] = useState(false);

  async function refresh(force: boolean) {
    setIsRefreshing(true);
    try {
      const payload = await refreshDatabase({
        force,
        trigger: "manual",
      });
      await mutate(payload, false);
    } finally {
      setIsRefreshing(false);
    }
  }

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24" />
        <Skeleton className="h-[640px]" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-3">
          <Badge variant="secondary" className="text-sm">
            SQLite Runtime
          </Badge>
          <div>
            <h1 className="text-2xl font-bold">Databases</h1>
            <p className="mt-2 max-w-3xl text-muted-foreground">
              Helaicopter uses SQLite for app-local metadata and the legacy
              DuckDB artifact for optional inspection/debugging. Conversations
              and analytics in the UI now stay fresh through simple polling.
            </p>
            <p className="text-sm text-muted-foreground">
              {data.scopeLabel ?? "Historical conversations before today from the last 365 days"}.
              DuckDB remains optional legacy inspection tooling when the artifact is present.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => refresh(false)}
            disabled={isRefreshing}
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
            Refresh Historical Snapshot
          </Button>
          <Button onClick={() => refresh(true)} disabled={isRefreshing}>
            <Database className="h-4 w-4" />
            Rebuild Historical Snapshot
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Refresh Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Badge variant={data.status === "failed" ? "destructive" : "secondary"}>
              {data.status}
            </Badge>
            <div className="text-sm text-muted-foreground">
              Last success: {formatTime(data.lastSuccessfulRefreshAt)}
            </div>
            <div className="text-sm text-muted-foreground">
              Trigger: {data.trigger ?? "unknown"}
            </div>
            <div className="text-sm text-muted-foreground">
              Idempotency key: {data.idempotencyKey?.slice(0, 12) ?? "n/a"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">SQLite</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <Badge variant={availabilityVariant(data.databases.sqlite.availability)}>
              {data.databases.sqlite.availability}
            </Badge>
            <div>{data.databases.sqlite.engine}</div>
            <div>{data.databases.sqlite.tableCount} tables</div>
            <div>{data.sourceConversationCount?.toLocaleString() ?? 0} conversations loaded</div>
            <div className="font-mono text-xs break-all">{data.databases.sqlite.path}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Legacy DuckDB</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <Badge variant={availabilityVariant(data.databases.legacyDuckdb.availability)}>
              {data.databases.legacyDuckdb.availability}
            </Badge>
            <div>{data.databases.legacyDuckdb.engine}</div>
            <div>{data.databases.legacyDuckdb.tableCount} tables</div>
            <div className="font-mono text-xs break-all">{data.databases.legacyDuckdb.path}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Serving Path</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <div>Analytics: {data.runtime.analyticsReadBackend}</div>
            <div>Conversation summaries: {data.runtime.conversationSummaryReadBackend}</div>
            <div>UI polling: every 3 seconds</div>
            <div>Window: last {data.windowDays ?? 365} days max</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Refresh Window</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <div>Started: {formatTime(data.startedAt)}</div>
            <div>Finished: {formatTime(data.finishedAt)}</div>
            <div>Window start: {formatTime(data.windowStart)}</div>
            <div>
              Duration: {data.durationMs ? `${(data.durationMs / 1000).toFixed(1)}s` : "n/a"}
            </div>
          </CardContent>
        </Card>
      </div>

      {data.error && (
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <TriangleAlert className="h-4 w-4" />
              Refresh Error
            </CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-sm text-muted-foreground">
            {data.error}
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="sqlite" className="space-y-4">
        <TabsList>
          <TabsTrigger value="sqlite">SQLite</TabsTrigger>
          <TabsTrigger value="legacyDuckdb">Legacy DuckDB</TabsTrigger>
        </TabsList>
        <TabsContent value="sqlite">
          <DatabaseExplorer database={data.databases.sqlite} />
        </TabsContent>
        <TabsContent value="legacyDuckdb">
          <div className="space-y-6">
            <LegacyDuckDbPreview database={data.databases.legacyDuckdb} />
            <DatabaseExplorer database={data.databases.legacyDuckdb} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
