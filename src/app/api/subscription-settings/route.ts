import { NextResponse } from "next/server";
import { getSubscriptionSettings, updateSubscriptionSettings } from "@/lib/subscription-settings";
import type { SupportedProvider } from "@/lib/types";

export async function GET() {
  return NextResponse.json(getSubscriptionSettings());
}

export async function PATCH(request: Request) {
  const body = await request.json().catch(() => ({}));
  const updates: Partial<
    Record<SupportedProvider, { hasSubscription: boolean; monthlyCost: number }>
  > = {};

  for (const provider of ["claude", "codex"] as const) {
    const entry = body?.[provider];
    if (!entry || typeof entry !== "object") {
      continue;
    }

    updates[provider] = {
      hasSubscription: Boolean(entry.hasSubscription),
      monthlyCost: Number(entry.monthlyCost ?? 0),
    };
  }

  return NextResponse.json(updateSubscriptionSettings(updates));
}
