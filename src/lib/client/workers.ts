"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";

import type { Worker } from "@/lib/types";
import * as endpoints from "@/lib/client/endpoints";
import { del, post, requestJson } from "@/lib/client/fetcher";
import { normalizeWorkers } from "@/lib/client/normalize";
import { workerListSchema } from "@/lib/client/schemas/workers";

const workerSwrOptions = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  refreshInterval: 5_000,
};

export function useWorkers(provider?: Worker["provider"]) {
  return useSWR<Worker[]>(
    endpoints.workers({ provider }),
    (url: string) => requestJson(url, undefined, workerListSchema, normalizeWorkers),
    workerSwrOptions
  );
}

function useWorkerAction(action: (id: string) => Promise<unknown>) {
  const { mutate } = useSWRConfig();
  const [pendingWorkerId, setPendingWorkerId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(workerId: string) {
    setPendingWorkerId(workerId);
    setError(null);
    try {
      await action(workerId);
      await mutate((key) => typeof key === "string" && key.includes("/workers"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Worker action failed.");
      throw cause;
    } finally {
      setPendingWorkerId(null);
    }
  }

  return {
    run,
    pendingWorkerId,
    error,
  };
}

export function useDrainWorker() {
  return useWorkerAction((workerId) => post(endpoints.workerDrain(workerId)));
}

export function useRemoveWorker() {
  return useWorkerAction((workerId) => del(endpoints.worker(workerId)));
}
