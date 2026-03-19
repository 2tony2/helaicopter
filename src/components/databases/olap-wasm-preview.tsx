"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { DatabaseArtifactStatus } from "@/lib/types";

const DUCKDB_WASM_ESM_URL =
  "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.33.1-dev20.0/+esm";

type DuckDbModule = {
  AsyncDuckDB: new (logger: unknown, worker: Worker) => DuckDbDatabase;
  VoidLogger: new () => unknown;
  DuckDBDataProtocol: {
    HTTP: number;
  };
  getJsDelivrBundles: () => unknown;
  selectBundle: (bundles: unknown) => Promise<{
    mainModule: string;
    mainWorker?: string;
    pthreadWorker?: string;
  }>;
};

type DuckDbConnection = {
  close: () => Promise<void>;
  query: (sql: string) => Promise<{ toArray: () => Record<string, unknown>[] }>;
};

type DuckDbDatabase = {
  instantiate: (mainModule: string, pthreadWorker?: string) => Promise<void>;
  registerFileURL: (
    name: string,
    url: string,
    protocol: number,
    directIO: boolean
  ) => Promise<void>;
  connect: () => Promise<DuckDbConnection>;
  terminate: () => Promise<void>;
};

export function DuckDbPreview({
  database,
}: Readonly<{
  database: DatabaseArtifactStatus;
}>) {
  const [selectedTable, setSelectedTable] = useState(database.tables[0]?.name ?? "");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState("Loading DuckDB preview...");

  useEffect(() => {
    setSelectedTable(database.tables[0]?.name ?? "");
  }, [database.tables]);

  useEffect(() => {
    let active = true;
    let connection: DuckDbConnection | null = null;
    let databaseHandle: DuckDbDatabase | null = null;
    let worker: Worker | null = null;
    let workerUrl: string | null = null;

    async function load() {
      if (!database.publicPath) {
        setRows([]);
        setStatus("DuckDB artifact is not available for browser preview.");
        return;
      }

      if (!selectedTable) {
        setRows([]);
        setStatus("No DuckDB tables available.");
        return;
      }

      setStatus("Loading DuckDB preview...");

      const duckdb = (await import(
        /* webpackIgnore: true */ DUCKDB_WASM_ESM_URL
      )) as DuckDbModule;
      const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
      workerUrl = URL.createObjectURL(
        new Blob([`importScripts("${bundle.mainWorker!}");`], {
          type: "text/javascript",
        })
      );
      worker = new Worker(workerUrl);

      const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
      await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
      await db.registerFileURL(
        "helaicopter_olap.duckdb",
        `${window.location.origin}${database.publicPath}`,
        duckdb.DuckDBDataProtocol.HTTP,
        false
      );

      const conn = await db.connect();
      await conn.query(`ATTACH 'helaicopter_olap.duckdb' AS helaicopter_olap (READ_ONLY)`);
      const result = await conn.query(
        `SELECT * FROM helaicopter_olap.main."${selectedTable.replaceAll('"', '""')}" LIMIT 25`
      );

      if (!active) {
        await conn.close();
        await db.terminate();
        return;
      }

      connection = conn;
      databaseHandle = db;
      setRows(result.toArray());
      setStatus(`Showing up to 25 rows from ${selectedTable}.`);
    }

    void load().catch((error) => {
      if (!active) return;
      setRows([]);
      setStatus(error instanceof Error ? error.message : "DuckDB preview failed to load.");
    });

    return () => {
      active = false;
      void connection?.close();
      void databaseHandle?.terminate();
      worker?.terminate();
      if (workerUrl) {
        URL.revokeObjectURL(workerUrl);
      }
    };
  }, [database.publicPath, selectedTable]);

  const columns = Object.keys(rows[0] ?? {});

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">DuckDB Artifact Preview</CardTitle>
        <CardDescription>
          Browser-side inspection of the DuckDB export artifact. This is
          not the primary analytics backend.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-muted-foreground">Preview table</span>
          <select
            className="h-10 rounded-md border bg-background px-3"
            value={selectedTable}
            onChange={(event) => setSelectedTable(event.target.value)}
          >
            {database.tables.map((table) => (
              <option key={table.name} value={table.name}>
                {table.name}
              </option>
            ))}
          </select>
        </label>

        <div className="text-sm text-muted-foreground">{status}</div>

        <div className="overflow-x-auto rounded-xl border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                {columns.map((column) => (
                  <th key={column} className="px-3 py-2 text-left font-medium">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className="border-t">
                  {columns.map((column) => (
                    <td key={`${index}:${column}`} className="px-3 py-2 align-top text-muted-foreground">
                      {row[column] == null ? "NULL" : String(row[column])}
                    </td>
                  ))}
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td className="px-3 py-6 text-muted-foreground" colSpan={Math.max(columns.length, 1)}>
                    No rows available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
