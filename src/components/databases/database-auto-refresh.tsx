"use client";

import { useEffect } from "react";
import { refreshDatabase } from "@/lib/client/mutations";

export function DatabaseAutoRefresh() {
  useEffect(() => {
    const refresh = () => {
      void refreshDatabase({
        force: false,
        trigger: "auto",
      }).catch(() => {
        // Background refresh failures surface through the status endpoint.
      });
    };

    refresh();
    const intervalId = window.setInterval(refresh, 21_600_000);
    return () => window.clearInterval(intervalId);
  }, []);

  return null;
}
