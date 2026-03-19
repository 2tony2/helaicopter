"use client";

import { formatDistanceToNowStrict } from "date-fns";
import { type ReactNode, useState } from "react";
import { Database, HardDrive, Layers2, RefreshCw, Server, TriangleAlert } from "lucide-react";
import { useDatabaseStatus } from "@/hooks/use-conversations";
import { refreshDatabase } from "@/lib/client/mutations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DatabaseArtifactStatus, DatabaseAvailability, DatabaseColumnSchema } from "@/lib/types";

function formatTime(value?: string | null): string {
  if (!value) return "Not available";
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
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs">{column.name}</span>
        <Badge variant="outline" className="text-[10px]">
          {column.type}
        </Badge>
        {column.isPrimaryKey ? (
          <Badge variant="secondary" className="text-[10px]">
            PK
          </Badge>
        ) : null}
        {!column.nullable ? (
          <Badge variant="secondary" className="text-[10px]">
            NOT NULL
          </Badge>
        ) : null}
      </div>
      {column.defaultValue || column.references ? (
        <div className="mt-2 space-y-1 text-xs text-muted-foreground">
          {column.defaultValue ? <div>Default: {column.defaultValue}</div> : null}
          {column.references ? <div>Ref: {column.references}</div> : null}
        </div>
      ) : null}
    </div>
  );
}

function MetricGrid({ database }: Readonly<{ database: DatabaseArtifactStatus }>) {
  const metrics = [
    { label: "Operational status", value: database.operationalStatus ?? "Not reported" },
    { label: "Inventory", value: database.inventorySummary ?? "Not reported" },
    { label: "Size", value: database.sizeDisplay ?? "Not available" },
    { label: "Tables", value: database.tableCount.toLocaleString() },
    ...database.load.map((metric) => ({
      label: metric.label,
      value: metric.displayValue ?? (metric.value != null ? String(metric.value) : "Not reported"),
    })),
  ];

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {metrics.map((metric) => (
        <div key={`${database.key}:${metric.label}`} className="rounded-xl border bg-muted/20 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            {metric.label}
          </div>
          <div className="mt-2 text-sm">{metric.value}</div>
        </div>
      ))}
    </div>
  );
}

function TableInventory({ database }: Readonly<{ database: DatabaseArtifactStatus }>) {
  if (database.tables.length === 0) {
    return (
      <div className="rounded-xl border bg-muted/20 p-6 text-sm text-muted-foreground">
        No table inventory available for this resource.
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      {database.tables.map((table) => (
        <div key={table.name} className="rounded-xl border p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-medium">{table.name}</div>
              <div className="text-xs text-muted-foreground">
                {table.columns.length} columns
              </div>
            </div>
            <div className="text-right text-xs text-muted-foreground">
              <div>{table.rowCount.toLocaleString()} rows</div>
              <div>{table.sizeDisplay ?? "Size unavailable"}</div>
            </div>
          </div>
          {table.columns.length > 0 ? (
            <div className="mt-3 grid gap-3">
              {table.columns.map((column) => (
                <ColumnChip key={`${table.name}:${column.name}`} column={column} />
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ResourceCard({
  title,
  icon,
  database,
}: Readonly<{
  title: string;
  icon: ReactNode;
  database: DatabaseArtifactStatus;
}>) {
  return (
    <Card className="border-border/70">
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="rounded-xl border bg-muted/20 p-2 text-muted-foreground">
              {icon}
            </div>
            <div>
              <CardTitle className="text-lg">{title}</CardTitle>
              <CardDescription>{database.engine}</CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={availabilityVariant(database.availability)}>
              {database.availability}
            </Badge>
            {database.health ? <Badge variant="outline">{database.health}</Badge> : null}
          </div>
        </div>
        {database.note ? (
          <div className="max-w-4xl text-sm text-muted-foreground">{database.note}</div>
        ) : null}
        {database.path || database.target ? (
          <div className="font-mono text-xs text-muted-foreground break-all">
            {database.path ?? database.target}
          </div>
        ) : null}
        {database.error ? (
          <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
            {database.error}
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-6">
        <MetricGrid database={database} />
        <div className="space-y-3">
          <div className="text-sm font-medium">Table Inventory</div>
          <TableInventory database={database} />
        </div>
      </CardContent>
    </Card>
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
        <Skeleton className="h-[800px]" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-3">
          <Badge variant="secondary" className="text-sm">
            Database And Cache Operations
          </Badge>
          <div>
            <h1 className="text-2xl font-bold">Databases and Caches Overview</h1>
            <p className="mt-2 max-w-3xl text-muted-foreground">
              Health, inventory, size, and operational load for the frontend short-term cache,
              the app SQLite store, the DuckDB inspection snapshot, and the Prefect Postgres
              backing service.
            </p>
            <p className="text-sm text-muted-foreground">
              {data.scopeLabel ?? "Historical conversations before today from the last 365 days"}.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => refresh(false)} disabled={isRefreshing}>
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
            Refresh Overview
          </Button>
          <Button onClick={() => refresh(true)} disabled={isRefreshing}>
            <Database className="h-4 w-4" />
            Rebuild Snapshot
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Refresh Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <Badge variant={data.status === "failed" ? "destructive" : "secondary"}>
              {data.status}
            </Badge>
            <div>Last success: {formatTime(data.lastSuccessfulRefreshAt)}</div>
            <div>Trigger: {data.trigger ?? "unknown"}</div>
            <div>Started: {formatTime(data.startedAt)}</div>
            <div>Finished: {formatTime(data.finishedAt)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Frontend Cache</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <Badge variant={availabilityVariant(data.databases.frontendCache.availability)}>
              {data.databases.frontendCache.availability}
            </Badge>
            <div>{data.databases.frontendCache.operationalStatus ?? "Not reported"}</div>
            <div>{data.databases.frontendCache.sizeDisplay ?? "No size reported"}</div>
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
            <div>{data.databases.sqlite.tableCount} tables</div>
            <div>{data.databases.sqlite.sizeDisplay ?? "No size reported"}</div>
            <div className="font-mono text-xs break-all">{data.databases.sqlite.path}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Prefect Postgres</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <Badge variant={availabilityVariant(data.databases.prefectPostgres.availability)}>
              {data.databases.prefectPostgres.availability}
            </Badge>
            <div>{data.databases.prefectPostgres.operationalStatus ?? "Not reported"}</div>
            <div className="font-mono text-xs break-all">
              {data.databases.prefectPostgres.target ?? "Target unavailable"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">DuckDB</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <Badge variant={availabilityVariant(data.databases.duckdb.availability)}>
              {data.databases.duckdb.availability}
            </Badge>
            <div>{data.databases.duckdb.tableCount} tables</div>
            <div>{data.databases.duckdb.sizeDisplay ?? "No size reported"}</div>
            <div className="font-mono text-xs break-all">{data.databases.duckdb.path}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Serving Path</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <div>Analytics: {data.runtime.analyticsReadBackend}</div>
            <div>Conversation summaries: {data.runtime.conversationSummaryReadBackend}</div>
            <div>Window: last {data.windowDays ?? 365} days max</div>
            <div>Source conversations: {data.sourceConversationCount?.toLocaleString() ?? "n/a"}</div>
          </CardContent>
        </Card>
      </div>

      {data.error ? (
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TriangleAlert className="h-4 w-4" />
              Refresh Error
            </CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-sm text-muted-foreground">
            {data.error}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6">
        <ResourceCard
          title="Frontend Short-Term Cache"
          icon={<Layers2 className="h-5 w-5" />}
          database={data.databases.frontendCache}
        />
        <ResourceCard
          title="SQLite Conversation Store"
          icon={<HardDrive className="h-5 w-5" />}
          database={data.databases.sqlite}
        />
        <ResourceCard
          title="Prefect Postgres"
          icon={<Server className="h-5 w-5" />}
          database={data.databases.prefectPostgres}
        />
        <ResourceCard
          title="DuckDB Inspection Snapshot"
          icon={<Database className="h-5 w-5" />}
          database={data.databases.duckdb}
        />
      </div>
    </div>
  );
}
