import Database from "better-sqlite3";
import { execFileSync } from "child_process";
import { existsSync } from "fs";
import { join } from "path";
import type {
  SubscriptionSettings,
  SupportedProvider,
} from "@/lib/types";

const OLTP_DB_PATH = join(
  process.cwd(),
  "public",
  "database-artifacts",
  "oltp",
  "helaicopter_oltp.sqlite"
);

const PROVIDERS: SupportedProvider[] = ["claude", "codex"];
const DEFAULT_MONTHLY_COST = 200;

type SubscriptionRow = {
  provider: SupportedProvider;
  has_subscription: number;
  monthly_cost: number;
  updated_at: string;
};

let databaseReady = false;

function ensureDatabaseReady() {
  if (databaseReady) {
    return;
  }

  execFileSync(
    "uv",
    ["run", "alembic", "-c", join(process.cwd(), "alembic.ini"), "-x", "target=oltp", "upgrade", "head"],
    {
      cwd: process.cwd(),
      stdio: "pipe",
    }
  );

  const db = new Database(OLTP_DB_PATH);
  db.pragma("journal_mode = WAL");
  db.pragma("busy_timeout = 5000");
  seedDefaults(db);
  db.close();
  databaseReady = true;
}

function openDb() {
  ensureDatabaseReady();
  const db = new Database(OLTP_DB_PATH);
  db.pragma("journal_mode = WAL");
  db.pragma("busy_timeout = 5000");
  return db;
}

function seedDefaults(db: Database.Database) {
  const now = new Date().toISOString();
  const statement = db.prepare(
    `
      INSERT OR IGNORE INTO subscription_settings (
        provider,
        has_subscription,
        monthly_cost,
        updated_at
      ) VALUES (?, 1, ?, ?)
    `
  );

  for (const provider of PROVIDERS) {
    statement.run(provider, DEFAULT_MONTHLY_COST, now);
  }
}

function mapRows(rows: SubscriptionRow[]): SubscriptionSettings {
  const now = new Date().toISOString();
  const defaults: SubscriptionSettings = {
    claude: {
      provider: "claude",
      hasSubscription: true,
      monthlyCost: DEFAULT_MONTHLY_COST,
      updatedAt: now,
    },
    codex: {
      provider: "codex",
      hasSubscription: true,
      monthlyCost: DEFAULT_MONTHLY_COST,
      updatedAt: now,
    },
  };

  for (const row of rows) {
    defaults[row.provider] = {
      provider: row.provider,
      hasSubscription: Boolean(row.has_subscription),
      monthlyCost: row.monthly_cost,
      updatedAt: row.updated_at,
    };
  }

  return defaults;
}

export function getSubscriptionSettings(): SubscriptionSettings {
  const db = openDb();
  try {
    const rows = db
      .prepare(
        `
          SELECT provider, has_subscription, monthly_cost, updated_at
          FROM subscription_settings
        `
      )
      .all() as SubscriptionRow[];
    return mapRows(rows);
  } finally {
    db.close();
  }
}

export function updateSubscriptionSettings(
  input: Partial<Record<SupportedProvider, { hasSubscription: boolean; monthlyCost: number }>>
): SubscriptionSettings {
  const db = openDb();
  const now = new Date().toISOString();

  try {
    const updateStatement = db.prepare(
      `
        UPDATE subscription_settings
        SET has_subscription = ?, monthly_cost = ?, updated_at = ?
        WHERE provider = ?
      `
    );

    for (const provider of PROVIDERS) {
      const update = input[provider];
      if (!update) continue;

      const monthlyCost = Number.isFinite(update.monthlyCost)
        ? Math.max(0, Math.round(update.monthlyCost * 100) / 100)
        : DEFAULT_MONTHLY_COST;

      updateStatement.run(
        update.hasSubscription ? 1 : 0,
        monthlyCost,
        now,
        provider
      );
    }

    return getSubscriptionSettings();
  } finally {
    db.close();
  }
}

export function subscriptionSettingsExist(): boolean {
  return existsSync(OLTP_DB_PATH);
}
