"use client";

import useSWR from "swr";

import type { OperatorBootstrapSummary } from "@/lib/types";
import * as endpoints from "@/lib/client/endpoints";
import { requestJson } from "@/lib/client/fetcher";
import { operatorBootstrapSchema } from "@/lib/client/schemas/operator-bootstrap";

const bootstrapSwrOptions = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  refreshInterval: 5_000,
};

export function useOperatorBootstrap() {
  return useSWR<OperatorBootstrapSummary>(
    endpoints.operatorBootstrap(),
    (url: string) => requestJson(url, undefined, operatorBootstrapSchema),
    bootstrapSwrOptions
  );
}
