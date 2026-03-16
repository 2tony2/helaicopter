import type { Metadata } from "next";
import { DatabaseDashboard } from "@/components/databases/database-dashboard";

export const metadata: Metadata = {
  title: "Databases | Helaicopter",
  description:
    "SQLite runtime status plus legacy DuckDB artifact inspection.",
};

export default function DatabasesPage() {
  return <DatabaseDashboard />;
}
