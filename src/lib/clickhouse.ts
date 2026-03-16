interface ClickHouseQueryResponse<Row> {
  data?: Row[];
  exception?: string;
}

export interface ClickHouseConnectionSettings {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  secure: boolean;
}

function readBooleanEnv(name: string, defaultValue = false): boolean {
  const value = process.env[name];
  if (!value) {
    return defaultValue;
  }

  return ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

function readIntegerEnv(name: string, defaultValue: number): number {
  const value = process.env[name];
  if (!value) {
    return defaultValue;
  }

  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : defaultValue;
}

export function getClickHouseSettings(): ClickHouseConnectionSettings {
  return {
    host: process.env.HELAICOPTER_CLICKHOUSE_HOST || "127.0.0.1",
    port: readIntegerEnv("HELAICOPTER_CLICKHOUSE_PORT", 8123),
    database: process.env.HELAICOPTER_CLICKHOUSE_DATABASE || "helaicopter",
    user: process.env.HELAICOPTER_CLICKHOUSE_USER || "helaicopter",
    password: process.env.HELAICOPTER_CLICKHOUSE_PASSWORD || "helaicopter",
    secure: readBooleanEnv("HELAICOPTER_CLICKHOUSE_SECURE", false),
  };
}

export function escapeClickHouseString(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll("'", "\\'");
}

export async function queryClickHouseRows<Row>(sql: string): Promise<Row[]> {
  const settings = getClickHouseSettings();
  const protocol = settings.secure ? "https" : "http";
  const url = new URL(
    `${protocol}://${settings.host}:${settings.port}/?database=${encodeURIComponent(
      settings.database
    )}`
  );
  const authToken = Buffer.from(`${settings.user}:${settings.password}`).toString(
    "base64"
  );
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Basic ${authToken}`,
      Accept: "application/json",
      "Content-Type": "text/plain; charset=utf-8",
    },
    body: `${sql.trim()}\nFORMAT JSON`,
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `ClickHouse query failed with ${response.status}: ${errorText.slice(0, 500)}`
    );
  }

  const payload = (await response.json()) as ClickHouseQueryResponse<Row>;
  if (payload.exception) {
    throw new Error(payload.exception);
  }

  return payload.data || [];
}
