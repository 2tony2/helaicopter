import type { Metadata } from "next";
import { DatabaseDashboard } from "@/components/databases/database-dashboard";

export const metadata: Metadata = {
  title: "Databases | Helaicopter",
  description:
    "SQLite OLTP and DuckDB OLAP schemas, refresh status, and SchemaSpy output.",
};

export default function DatabasesPage() {
  return <DatabaseDashboard />;
}
