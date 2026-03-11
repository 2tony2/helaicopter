"use client";

import useSWR from "swr";
import type { PlanSummary, PlanDetail } from "@/lib/types";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const swrOptions = {
  revalidateOnFocus: false,
};

export function usePlans() {
  return useSWR<PlanSummary[]>("/api/plans", fetcher, swrOptions);
}

export function usePlan(slug?: string) {
  return useSWR<PlanDetail>(slug ? `/api/plans/${slug}` : null, fetcher, swrOptions);
}
