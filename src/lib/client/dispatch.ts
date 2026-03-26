"use client";

import useSWR from "swr";

import type { DispatchHistoryEntry, DispatchQueueSnapshot } from "@/lib/types";
import * as endpoints from "@/lib/client/endpoints";
import { requestJson } from "@/lib/client/fetcher";
import {
  normalizeDispatchHistory,
  normalizeDispatchQueueSnapshot,
} from "@/lib/client/normalize";
import {
  dispatchHistorySchema,
  dispatchQueueSnapshotSchema,
} from "@/lib/client/schemas/dispatch";

const dispatchSwrOptions = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  refreshInterval: 5_000,
};

export function useDispatchQueue() {
  return useSWR<DispatchQueueSnapshot>(
    endpoints.dispatchQueue(),
    (url: string) =>
      requestJson(url, undefined, dispatchQueueSnapshotSchema, normalizeDispatchQueueSnapshot),
    dispatchSwrOptions
  );
}

export function useDispatchHistory(limit = 25) {
  return useSWR<DispatchHistoryEntry[]>(
    endpoints.dispatchHistory({ limit }),
    (url: string) => requestJson(url, undefined, dispatchHistorySchema, normalizeDispatchHistory),
    dispatchSwrOptions
  );
}
