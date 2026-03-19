import type { Metadata } from "next";
import { DatabaseDashboard } from "@/components/databases/database-dashboard";

export const metadata: Metadata = {
  title: "Databases | Helaicopter",
  description:
    "Operational overview for the frontend cache, SQLite, and Prefect Postgres.",
};

export default function DatabasesPage() {
  return <DatabaseDashboard />;
}
