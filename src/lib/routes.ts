import {
  conversationDetailTabs,
  orchestrationTabs,
  resolveConversationDetailTab,
  resolveOrchestrationInitialTab,
  type ConversationDetailTab,
  type OrchestrationTab,
} from "./client/schemas/runtime.ts";

export {
  conversationDetailTabs,
  orchestrationTabs,
  resolveConversationDetailTab,
  resolveOrchestrationInitialTab,
};
export type { ConversationDetailTab, OrchestrationTab };

export type ConversationRouteProvider = "claude" | "codex" | "openclaw" | "opencloud";

export type ConversationCanonicalTarget =
  | {
      tab: "messages";
      messageId?: string;
    }
  | {
      tab: "plans";
      planId?: string;
    }
  | {
      tab: "subagents";
      agentId?: string;
    }
  | {
      tab: Exclude<ConversationDetailTab, "messages" | "plans" | "subagents">;
    };

export type ConversationRouteParseResult =
  | {
      kind: "canonical";
      conversationRef: string;
      routeSlug: string;
      provider: ConversationRouteProvider;
      sessionId: string;
      tab: ConversationDetailTab;
      isBaseRoute: boolean;
      messageId?: string;
      planId?: string;
      agentId?: string;
    }
  | {
      kind: "legacy";
      projectPath: string;
      sessionId: string;
      agentId?: string;
    }
  | {
      kind: "invalid";
    };

export type ConversationRouteDecision =
  | {
      kind: "render";
      conversationRef: string;
      tab: ConversationDetailTab;
      messageId?: string;
      planId?: string;
      agentId?: string;
    }
  | {
      kind: "redirect";
      href: string;
    }
  | {
      kind: "not-found";
    };

const canonicalConversationProviders = ["claude", "codex", "openclaw", "opencloud"] as const;

type ParsedConversationRef = {
  conversationRef: string;
  routeSlug: string;
  provider: ConversationRouteProvider;
  sessionId: string;
};

type LegacyConversationRouteState = {
  tab?: ConversationDetailTab;
  plan?: string;
  subagent?: string;
  message?: string;
};

type ConversationRouteDecisionOptions = {
  resolution?: {
    conversationRef: string;
  };
  searchParams?: URLSearchParams;
  validMessageIds?: Iterable<string>;
  validPlanIds?: Iterable<string>;
  validAgentIds?: Iterable<string>;
};

function normalizeLegacyEntityId(value?: string | null): string | undefined {
  if (!value) {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function looksLikeLegacySessionId(value: string): boolean {
  return value.includes("-");
}

function encodePathSegment(value: string): string {
  return encodeURIComponent(value);
}

function buildConversationRouteFromTarget(
  conversationRef: string,
  target: ConversationCanonicalTarget
): string {
  switch (target.tab) {
    case "messages":
      return target.messageId
        ? buildConversationMessageRoute(conversationRef, target.messageId)
        : buildConversationTabRoute(conversationRef, "messages");
    case "plans":
      return target.planId
        ? buildConversationPlanRoute(conversationRef, target.planId)
        : buildConversationTabRoute(conversationRef, "plans");
    case "subagents":
      return target.agentId
        ? buildConversationSubagentTabRoute(conversationRef, target.agentId)
        : buildConversationTabRoute(conversationRef, "subagents");
    default:
      return buildConversationTabRoute(conversationRef, target.tab);
  }
}

export function buildCanonicalConversationRoute(
  conversationRef: string,
  target: ConversationCanonicalTarget
): string {
  return buildConversationRouteFromTarget(conversationRef, target);
}

function buildLegacyConversationQuery(target: ConversationCanonicalTarget): string {
  const params = new URLSearchParams();
  if (target.tab !== "messages") {
    params.set("tab", target.tab);
  }
  if (target.tab === "messages" && target.messageId) {
    params.set("message", target.messageId);
  }
  if (target.tab === "plans" && target.planId) {
    params.set("plan", target.planId);
  }
  if (target.tab === "subagents" && target.agentId) {
    params.set("subagent", target.agentId);
  }
  return params.toString();
}

function normalizeLegacyBuilderTarget(state?: LegacyConversationRouteState): ConversationCanonicalTarget {
  const explicitTab = state?.tab;
  const messageId = normalizeLegacyEntityId(state?.message);
  const planId = normalizeLegacyEntityId(state?.plan);
  const agentId = normalizeLegacyEntityId(state?.subagent);

  if (explicitTab === "messages") {
    return messageId ? { tab: "messages", messageId } : { tab: "messages" };
  }
  if (explicitTab === "plans") {
    return planId ? { tab: "plans", planId } : { tab: "plans" };
  }
  if (explicitTab === "subagents") {
    return agentId ? { tab: "subagents", agentId } : { tab: "subagents" };
  }
  if (explicitTab) {
    return { tab: explicitTab };
  }

  if (messageId) {
    return { tab: "messages", messageId };
  }
  if (planId) {
    return { tab: "plans", planId };
  }
  if (agentId) {
    return { tab: "subagents", agentId };
  }

  return { tab: "messages" };
}

function parseConversationRef(conversationRef: string): ParsedConversationRef | null {
  const separatorIndex = conversationRef.indexOf("--");
  if (separatorIndex <= 0 || separatorIndex === conversationRef.length - 2) {
    return null;
  }

  const routeSlug = conversationRef.slice(0, separatorIndex);
  const tail = conversationRef.slice(separatorIndex + 2);
  const hyphenIndex = tail.indexOf("-");
  if (hyphenIndex <= 0 || hyphenIndex === tail.length - 1) {
    return null;
  }

  const provider = tail.slice(0, hyphenIndex);
  const sessionId = tail.slice(hyphenIndex + 1);

  if (
    !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(routeSlug) ||
    !(canonicalConversationProviders as readonly string[]).includes(provider) ||
    !sessionId
  ) {
    return null;
  }

  return {
    conversationRef,
    routeSlug,
    provider: provider as ConversationRouteProvider,
    sessionId,
  };
}

function isValidCanonicalNestedTab(tab: ConversationDetailTab): tab is "messages" | "plans" | "subagents" {
  return tab === "messages" || tab === "plans" || tab === "subagents";
}

function collectionHasValue(values: Iterable<string> | undefined, target: string): boolean {
  if (!values) {
    return true;
  }
  for (const value of values) {
    if (value === target) {
      return true;
    }
  }
  return false;
}

function canonicalTargetFromParsedRoute(
  route: Extract<ConversationRouteParseResult, { kind: "canonical" }>
): ConversationCanonicalTarget {
  if (route.tab === "messages") {
    return route.messageId ? { tab: "messages", messageId: route.messageId } : { tab: "messages" };
  }
  if (route.tab === "plans") {
    return route.planId ? { tab: "plans", planId: route.planId } : { tab: "plans" };
  }
  if (route.tab === "subagents") {
    return route.agentId ? { tab: "subagents", agentId: route.agentId } : { tab: "subagents" };
  }
  return { tab: route.tab };
}

function legacyRouteStateToSearchParams(state?: LegacyConversationRouteState): URLSearchParams {
  const params = new URLSearchParams();
  if (state?.tab) {
    params.set("tab", state.tab);
  }
  if (state?.plan) {
    params.set("plan", state.plan);
  }
  if (state?.subagent) {
    params.set("subagent", state.subagent);
  }
  if (state?.message) {
    params.set("message", state.message);
  }
  return params;
}

export function buildConversationBaseRoute(conversationRef: string): string {
  return `/conversations/${encodePathSegment(conversationRef)}`;
}

export function buildConversationTabRoute(
  conversationRef: string,
  tab: ConversationDetailTab
): string {
  return `${buildConversationBaseRoute(conversationRef)}/${encodePathSegment(tab)}`;
}

export function buildConversationMessageRoute(
  conversationRef: string,
  messageId: string
): string {
  return `${buildConversationTabRoute(conversationRef, "messages")}/${encodePathSegment(messageId)}`;
}

export function buildConversationPlanRoute(conversationRef: string, planId: string): string {
  return `${buildConversationTabRoute(conversationRef, "plans")}/${encodePathSegment(planId)}`;
}

export function buildConversationSubagentTabRoute(
  parentConversationRef: string,
  agentId: string
): string {
  return `${buildConversationTabRoute(parentConversationRef, "subagents")}/${encodePathSegment(agentId)}`;
}

function parseCanonicalConversationRouteSegments(
  segments: readonly string[]
): Extract<ConversationRouteParseResult, { kind: "canonical" }> | null {
  const [first, second, third, fourth] = segments;
  if (!first) {
    return null;
  }

  const parsedRef = parseConversationRef(first);
  if (!parsedRef) {
    return null;
  }

  if (!second) {
    return {
      kind: "canonical",
      ...parsedRef,
      tab: "messages",
      isBaseRoute: true,
    };
  }

  if (!(conversationDetailTabs as readonly string[]).includes(second)) {
    return null;
  }

  const tab = second as ConversationDetailTab;
  if (!third) {
    return {
      kind: "canonical",
      ...parsedRef,
      tab,
      isBaseRoute: false,
    };
  }

  if (fourth || !isValidCanonicalNestedTab(tab)) {
    return null;
  }

  const nestedId = normalizeLegacyEntityId(third);
  if (!nestedId) {
    return null;
  }

  if (tab === "messages") {
    return {
      kind: "canonical",
      ...parsedRef,
      tab,
      isBaseRoute: false,
      messageId: nestedId,
    };
  }

  if (tab === "plans") {
    return {
      kind: "canonical",
      ...parsedRef,
      tab,
      isBaseRoute: false,
      planId: nestedId,
    };
  }

  return {
    kind: "canonical",
    ...parsedRef,
    tab,
    isBaseRoute: false,
    agentId: nestedId,
  };
}

function parseLegacyConversationRouteSegments(
  segments: readonly string[]
): Extract<ConversationRouteParseResult, { kind: "legacy" }> | null {
  const [first, second, third, fourth] = segments;

  if (!first || !second) {
    return null;
  }

  if (!looksLikeLegacySessionId(second)) {
    return null;
  }

  if (segments.length === 2) {
    return {
      kind: "legacy",
      projectPath: first,
      sessionId: second,
    };
  }

  if (segments.length === 4 && third === "subagents") {
    const agentId = normalizeLegacyEntityId(fourth);
    if (!agentId) {
      return null;
    }
    return {
      kind: "legacy",
      projectPath: first,
      sessionId: second,
      agentId,
    };
  }

  return null;
}

export function parseConversationRouteSegments(
  segments: readonly string[]
): ConversationRouteParseResult {
  const canonicalRoute = parseCanonicalConversationRouteSegments(segments);
  if (canonicalRoute) {
    return canonicalRoute;
  }

  const legacyRoute = parseLegacyConversationRouteSegments(segments);
  if (legacyRoute) {
    return legacyRoute;
  }

  return { kind: "invalid" };
}

export function translateLegacyConversationRouteTarget(
  searchParams: URLSearchParams,
  legacyNestedAgentId?: string
): ConversationCanonicalTarget {
  const explicitTab = resolveConversationDetailTab(searchParams.get("tab") ?? undefined);
  const messageId = normalizeLegacyEntityId(searchParams.get("message"));
  const planId = normalizeLegacyEntityId(searchParams.get("plan"));
  const agentId =
    normalizeLegacyEntityId(legacyNestedAgentId) ??
    normalizeLegacyEntityId(searchParams.get("subagent"));

  if (explicitTab === "messages" && messageId) {
    return { tab: "messages", messageId };
  }
  if (explicitTab === "plans" && planId) {
    return { tab: "plans", planId };
  }
  if (explicitTab === "subagents" && agentId) {
    return { tab: "subagents", agentId };
  }

  if (messageId) {
    return { tab: "messages", messageId };
  }
  if (planId) {
    return { tab: "plans", planId };
  }
  if (agentId) {
    return { tab: "subagents", agentId };
  }

  return { tab: explicitTab };
}

export function decideConversationRoute(
  route: ConversationRouteParseResult,
  opts: ConversationRouteDecisionOptions = {}
): ConversationRouteDecision {
  if (route.kind === "invalid") {
    return { kind: "not-found" };
  }

  if (route.kind === "legacy") {
    const conversationRef = opts.resolution?.conversationRef;
    if (!conversationRef) {
      return { kind: "not-found" };
    }
    const target = translateLegacyConversationRouteTarget(
      opts.searchParams ?? new URLSearchParams(),
      route.agentId
    );
    return {
      kind: "redirect",
      href: buildConversationRouteFromTarget(conversationRef, target),
    };
  }

  const canonicalConversationRef = opts.resolution?.conversationRef ?? route.conversationRef;
  if (canonicalConversationRef !== route.conversationRef) {
    return {
      kind: "redirect",
      href: buildConversationRouteFromTarget(
        canonicalConversationRef,
        canonicalTargetFromParsedRoute(route)
      ),
    };
  }

  if (route.isBaseRoute) {
    return {
      kind: "redirect",
      href: buildConversationTabRoute(canonicalConversationRef, "messages"),
    };
  }

  if (route.messageId && !collectionHasValue(opts.validMessageIds, route.messageId)) {
    return { kind: "not-found" };
  }
  if (route.planId && !collectionHasValue(opts.validPlanIds, route.planId)) {
    return { kind: "not-found" };
  }
  if (route.agentId && !collectionHasValue(opts.validAgentIds, route.agentId)) {
    return { kind: "not-found" };
  }

  const decision: Extract<ConversationRouteDecision, { kind: "render" }> = {
    kind: "render",
    conversationRef: canonicalConversationRef,
    tab: route.tab,
  };

  if (route.messageId) {
    decision.messageId = route.messageId;
  }
  if (route.planId) {
    decision.planId = route.planId;
  }
  if (route.agentId) {
    decision.agentId = route.agentId;
  }

  return decision;
}

export function getConversationRouteState(
  searchParams: URLSearchParams,
  initial?: LegacyConversationRouteState
): {
  tab: ConversationDetailTab;
  plan?: string;
  subagent?: string;
  message?: string;
} {
  const mergedParams = legacyRouteStateToSearchParams(initial);
  for (const [key, value] of searchParams.entries()) {
    mergedParams.set(key, value);
  }

  const plan = mergedParams.get("plan") ?? initial?.plan;
  const subagent = mergedParams.get("subagent") ?? initial?.subagent;
  const message = mergedParams.get("message") ?? initial?.message;

  return {
    tab: resolveConversationDetailTab(mergedParams.get("tab") ?? initial?.tab),
    plan: plan ?? undefined,
    subagent: subagent ?? undefined,
    message: message ?? undefined,
  };
}

export function buildConversationRoute(
  projectPath: string,
  sessionId: string,
  opts?: LegacyConversationRouteState
): string {
  const target = normalizeLegacyBuilderTarget(opts);
  const query = buildLegacyConversationQuery(target);
  const path = `/conversations/${projectPath}/${sessionId}`;
  return query ? `${path}?${query}` : path;
}

export function buildConversationSubagentRoute(
  projectPath: string,
  sessionId: string,
  agentId: string
): string {
  return `/conversations/${projectPath}/${sessionId}/subagents/${agentId}`;
}

export function buildOrchestrationRoute(opts?: {
  tab?: OrchestrationTab;
  flowRunId?: string;
}): string {
  const params = new URLSearchParams();
  if (opts?.tab && opts.tab !== "orchestration") {
    params.set("tab", opts.tab);
  }
  if (opts?.flowRunId) {
    params.set("flowRunId", opts.flowRunId);
  }
  const query = params.toString();
  return query ? `/orchestration?${query}` : "/orchestration";
}

export function getOrchestrationRouteState(
  searchParams: URLSearchParams,
  initial?: {
    tab?: string;
    flowRunId?: string;
  }
): {
  tab: OrchestrationTab;
  flowRunId?: string;
} {
  const flowRunId = searchParams.get("flowRunId") ?? initial?.flowRunId;

  return {
    tab: resolveOrchestrationInitialTab(searchParams.get("tab") ?? initial?.tab),
    flowRunId: flowRunId ?? undefined,
  };
}
