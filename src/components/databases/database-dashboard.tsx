"use client";

import { formatDistanceToNowStrict } from "date-fns";
import { useState } from "react";
import { Database, RefreshCw, TriangleAlert } from "lucide-react";
import { useDatabaseStatus } from "@/hooks/use-conversations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { OlapWasmPreview } from "@/components/databases/olap-wasm-preview";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  DatabaseArtifactStatus,
  DatabaseColumnSchema,
  DatabaseStatus,
} from "@/lib/types";

function formatTime(value?: string | null): string {
  if (!value) return "Not refreshed yet";
  const date = new Date(value);
  return `${date.toLocaleString()} (${formatDistanceToNowStrict(date, { addSuffix: true })})`;
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
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1.35fr)]">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Table Explorer</CardTitle>
          <CardDescription>
            SQLAlchemy-inspected schema for {database.engine}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 max-h-[720px] overflow-y-auto pr-2">
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

      <Card>
        <CardHeader>
          <CardTitle className="text-base">SchemaSpy</CardTitle>
          <CardDescription>
            Live HTML docs generated from the current database artifact.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
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
          <iframe
            key={database.docsUrl}
            src={database.docsUrl}
            title={`${database.label} schema`}
            className="h-[680px] w-full rounded-xl border bg-background"
          />
        </CardContent>
      </Card>
    </div>
  );
}

export function DatabaseDashboard() {
  const { data, isLoading, mutate } = useDatabaseStatus();
  const [isRefreshing, setIsRefreshing] = useState(false);

  async function refresh(force: boolean) {
    setIsRefreshing(true);
    try {
      const response = await fetch("/api/databases/refresh", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          force,
          trigger: "manual",
        }),
      });
      const payload = (await response.json()) as DatabaseStatus;
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
            SQLAlchemy + Alembic + SchemaSpy
          </Badge>
          <div>
            <h1 className="text-2xl font-bold">Databases</h1>
            <p className="mt-2 max-w-3xl text-muted-foreground">
              Historical parser output now lands in a normalized SQLite OLTP store
              and a DuckDB OLAP warehouse. The historical databases refresh every
              6 hours, while today&apos;s conversations stay live from the raw parser path.
            </p>
            <p className="text-sm text-muted-foreground">
              {data.scopeLabel ?? "Historical conversations before today from the last 365 days"}.
              Today is intentionally excluded from the warehouse refresh so the UI can stay realtime.
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
            Refresh Historical Data
          </Button>
          <Button onClick={() => refresh(true)} disabled={isRefreshing}>
            <Database className="h-4 w-4" />
            Recalculate Historical Data
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
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
            <CardTitle className="text-base">OLTP</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <div>{data.databases.oltp.engine}</div>
            <div>{data.databases.oltp.tableCount} tables</div>
            <div>{data.sourceConversationCount?.toLocaleString() ?? 0} conversations loaded</div>
            <div className="font-mono text-xs break-all">{data.databases.oltp.path}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">OLAP</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <div>{data.databases.olap.engine}</div>
            <div>{data.databases.olap.tableCount} tables</div>
            <div>Window: last {data.windowDays ?? 365} days max</div>
            <div className="font-mono text-xs break-all">{data.databases.olap.path}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Runtime</CardTitle>
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
        {data.clickhouseBackfill && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">ClickHouse Backfill</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <Badge
                variant={data.clickhouseBackfill.status === "failed" ? "destructive" : "secondary"}
              >
                {data.clickhouseBackfill.status}
              </Badge>
              <div>
                Events:{" "}
                {(data.clickhouseBackfill.rowsLoaded?.conversationEvents ?? 0).toLocaleString()} conv
                {" / "}
                {(data.clickhouseBackfill.rowsLoaded?.messageEvents ?? 0).toLocaleString()} msg
              </div>
              <div>
                Tools: {(data.clickhouseBackfill.rowsLoaded?.toolEvents ?? 0).toLocaleString()}
                {" / "}Usage: {(data.clickhouseBackfill.rowsLoaded?.usageEvents ?? 0).toLocaleString()}
              </div>
              <div className="font-mono text-xs break-all">{data.clickhouseBackfill.target}</div>
            </CardContent>
          </Card>
        )}
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

      {data.clickhouseBackfill?.error && (
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <TriangleAlert className="h-4 w-4" />
              ClickHouse Backfill Error
            </CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-sm text-muted-foreground">
            {data.clickhouseBackfill.error}
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="oltp" className="space-y-4">
        <TabsList>
          <TabsTrigger value="oltp">SQLite OLTP</TabsTrigger>
          <TabsTrigger value="olap">DuckDB OLAP</TabsTrigger>
        </TabsList>
        <TabsContent value="oltp">
          <DatabaseExplorer database={data.databases.oltp} />
        </TabsContent>
        <TabsContent value="olap">
          <div className="space-y-6">
            <OlapWasmPreview database={data.databases.olap} />
            <DatabaseExplorer database={data.databases.olap} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
