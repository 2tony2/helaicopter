import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { ConversationViewer } from "@/components/conversation/conversation-viewer";
import {
  decideConversationRoute,
  parseConversationRouteSegments,
  type ConversationDetailTab,
  type ConversationRouteDecision,
} from "@/lib/routes";
import { projectDirToDisplayName } from "@/lib/path-encoding";
import {
  normalizeConversationDetail,
  normalizeConversationRouteResolution,
} from "@/lib/client/normalize";
import { fetchBackendJson } from "@/lib/server/backend-api";
import { notFound, redirect } from "next/navigation";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type SearchParamsInput =
  | URLSearchParams
  | Record<string, string | string[] | undefined>
  | undefined;

type ConversationPageRequest = {
  segments: string[];
  searchParams?: SearchParamsInput;
};

type ConversationPageRenderResult = {
  kind: "render";
  breadcrumbs: Array<{
    href?: string;
    label: string;
    title?: string;
  }>;
  viewer: {
    conversationRef: string;
    projectPath: string;
    sessionId: string;
    parentSessionId?: string;
    initialTab: ConversationDetailTab;
    initialPlanId?: string;
    initialSubagentId?: string;
    initialMessageId?: string;
  };
};

export type ConversationPageDependencies = {
  fetchJson: typeof fetchBackendJson;
  redirect: (href: string) => never;
  notFound: () => never;
};

function toUrlSearchParams(input?: SearchParamsInput): URLSearchParams {
  if (!input) {
    return new URLSearchParams();
  }
  if (input instanceof URLSearchParams) {
    return input;
  }

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(input)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        params.append(key, item);
      }
      continue;
    }
    if (value !== undefined) {
      params.set(key, value);
    }
  }
  return params;
}

function getDecisionEntityIds(
  decision: Extract<ConversationRouteDecision, { kind: "render" }>
): {
  validMessageIds?: string[];
  validPlanIds?: string[];
  validAgentIds?: string[];
} {
  return {
    validMessageIds: decision.messageId ? [decision.messageId] : undefined,
    validPlanIds: decision.planId ? [decision.planId] : undefined,
    validAgentIds: decision.agentId ? [decision.agentId] : undefined,
  };
}

async function resolveConversationByRef(
  deps: ConversationPageDependencies,
  conversationRef: string
) {
  const response = await deps.fetchJson<unknown>(
    `/conversations/by-ref/${encodeURIComponent(conversationRef)}`
  );
  if (response.status === 404 || !response.data) {
    return null;
  }
  return normalizeConversationRouteResolution(response.data);
}

async function fetchConversationDetail(
  deps: ConversationPageDependencies,
  projectPath: string,
  sessionId: string,
  parentSessionId?: string
) {
  const query = parentSessionId
    ? `?parent_session_id=${encodeURIComponent(parentSessionId)}`
    : "";
  const response = await deps.fetchJson<unknown>(
    `/conversations/${encodeURIComponent(projectPath)}/${sessionId}${query}`
  );
  if (response.status === 404 || !response.data) {
    return null;
  }
  return normalizeConversationDetail(response.data);
}

function buildRenderResult(
  decision: Extract<ConversationRouteDecision, { kind: "render" }>,
  resolution: ReturnType<typeof normalizeConversationRouteResolution>,
  projectPath?: string,
  sessionId?: string
): ConversationPageRenderResult {
  const resolvedProjectPath = projectPath ?? resolution.projectPath;
  const resolvedSessionId = sessionId ?? resolution.sessionId;
  const displayName = projectDirToDisplayName(resolvedProjectPath);

  return {
    kind: "render",
    breadcrumbs: [
      { href: "/conversations", label: "Conversations" },
      { label: displayName, title: resolvedProjectPath },
      { label: `${resolvedSessionId.slice(0, 8)}...` },
    ],
    viewer: {
      conversationRef: resolution.conversationRef,
      projectPath: resolvedProjectPath,
      sessionId: resolvedSessionId,
      parentSessionId: resolution.parentSessionId,
      initialTab: decision.tab,
      initialMessageId: decision.messageId,
      initialPlanId: decision.planId,
      initialSubagentId: decision.agentId,
    },
  };
}

export function createConversationPageHandler(deps: ConversationPageDependencies) {
  return async function handleConversationPage({
    segments,
    searchParams,
  }: ConversationPageRequest): Promise<ConversationPageRenderResult> {
    const route = parseConversationRouteSegments(segments);
    const params = toUrlSearchParams(searchParams);

    if (route.kind === "invalid") {
      return deps.notFound();
    }

    if (route.kind === "legacy") {
      const legacyConversation = await fetchConversationDetail(
        deps,
        route.projectPath,
        route.sessionId
      );
      if (!legacyConversation?.conversationRef) {
        return deps.notFound();
      }

      const decision = decideConversationRoute(route, {
        resolution: { conversationRef: legacyConversation.conversationRef },
        searchParams: params,
      });

      if (decision.kind !== "redirect") {
        return deps.notFound();
      }
      return deps.redirect(decision.href);
    }

    const resolution = await resolveConversationByRef(deps, route.conversationRef);
    if (!resolution) {
      return deps.notFound();
    }

    const initialDecision = decideConversationRoute(route, {
      resolution: { conversationRef: resolution.conversationRef },
    });

    if (initialDecision.kind === "redirect") {
      return deps.redirect(initialDecision.href);
    }
    if (initialDecision.kind === "not-found") {
      return deps.notFound();
    }

    if (
      initialDecision.messageId === undefined &&
      initialDecision.planId === undefined &&
      initialDecision.agentId === undefined
    ) {
      return buildRenderResult(initialDecision, resolution);
    }

    const conversation = await fetchConversationDetail(
      deps,
      resolution.projectPath,
      resolution.sessionId,
      resolution.parentSessionId
    );
    if (!conversation) {
      return deps.notFound();
    }

    const validatedDecision = decideConversationRoute(route, {
      resolution: { conversationRef: resolution.conversationRef },
      ...getDecisionEntityIds(initialDecision),
    });

    if (validatedDecision.kind === "redirect") {
      return deps.redirect(validatedDecision.href);
    }
    if (validatedDecision.kind === "not-found") {
      return deps.notFound();
    }

    const validMessageIds = conversation.messages.map((message) => message.id);
    const validPlanIds = conversation.plans.map((plan) => plan.id);
    const validAgentIds = conversation.subagents.map((agent) => agent.agentId);

    const finalDecision = decideConversationRoute(route, {
      resolution: { conversationRef: resolution.conversationRef },
      validMessageIds,
      validPlanIds,
      validAgentIds,
    });

    if (finalDecision.kind === "redirect") {
      return deps.redirect(finalDecision.href);
    }
    if (finalDecision.kind === "not-found") {
      return deps.notFound();
    }

    return buildRenderResult(
      finalDecision,
      resolution,
      conversation.projectPath,
      conversation.sessionId
    );
  };
}

const handleConversationPage = createConversationPageHandler({
  fetchJson: fetchBackendJson,
  redirect,
  notFound,
});

export default async function ConversationCatchAllPage({
  params,
  searchParams,
}: {
  params: Promise<{ segments?: string[] }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ segments }, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const result = await handleConversationPage({
    segments: segments ?? [],
    searchParams: resolvedSearchParams,
  });

  return (
    <div className="space-y-8">
      <Breadcrumbs
        items={[
          { href: result.breadcrumbs[0]?.href ?? "/conversations", label: result.breadcrumbs[0]?.label ?? "Conversations" },
          {
            label: (
              <span
                title={result.breadcrumbs[1]?.title}
                className="truncate max-w-xs inline-block"
              >
                {result.breadcrumbs[1]?.label}
              </span>
            ),
          },
          {
            label: (
              <span className="font-mono text-xs">
                {result.breadcrumbs[2]?.label}
              </span>
            ),
          },
        ]}
      />

      <ConversationViewer {...result.viewer} />
    </div>
  );
}
