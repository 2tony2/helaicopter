"use client";

import { useEffect } from "react";

export function DatabaseAutoRefresh() {
  useEffect(() => {
    const refresh = () => {
      void fetch("/api/databases/refresh", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          force: false,
          trigger: "auto",
        }),
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
