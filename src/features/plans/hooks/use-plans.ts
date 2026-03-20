"use client";

import useSWR from "swr";
import type { PlanDetail, PlanSummary } from "@/lib/types";
import * as endpoints from "@/lib/client/endpoints";
import { requestJson } from "@/lib/client/fetcher";
import { normalizePlan, normalizePlans } from "@/lib/client/normalize";

const swrOptions = {
  revalidateOnFocus: false,
};

export function usePlans() {
  return useSWR<PlanSummary[]>(
    endpoints.plans(),
    // Rollout note: keep plans on the legacy normalize-only fetch path for this schema adoption step.
    (url: string) => requestJson(url, undefined, normalizePlans),
    swrOptions
  );
}

export function usePlan(slug?: string) {
  return useSWR<PlanDetail>(
    slug ? endpoints.plan(slug) : null,
    // Rollout note: keep plan detail on the legacy normalize-only fetch path for this schema adoption step.
    (url: string) => requestJson(url, undefined, normalizePlan),
    swrOptions
  );
}
