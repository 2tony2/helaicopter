import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import React from "react";

import {
  createConversationPageHandler,
  type ConversationPageDependencies,
} from "./page.tsx";
import {
  ProviderFilter,
  providerFilterOptions,
} from "../../../components/ui/provider-filter.tsx";
import {
  providerLabel as conversationProviderLabel,
  hasFatalConversationLoadError,
  resolveConversationProvider,
} from "../../../components/conversation/conversation-viewer.tsx";
import { matchesConversationProvider } from "../../../components/conversation/conversation-list.tsx";
import { resolveConversationDetailTab } from "../../../lib/routes.ts";

const canonicalRef = "review-the-backend-rollout--claude-claude-session-1";
const wrongSlugRef = "stale-slug--claude-claude-session-1";
const projectPath = "-Users-tony-Code-helaicopter";
const sessionId = "claude-session-1";

type FetchCall = {
  path: string;
  init?: RequestInit;
};

function makeResolution(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    conversation_ref: canonicalRef,
    route_slug: "review-the-backend-rollout",
    project_path: projectPath,
    session_id: sessionId,
    thread_type: "main",
    ...overrides,
  };
}

function makeConversationDetail(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    session_id: sessionId,
    project_path: projectPath,
    route_slug: "review-the-backend-rollout",
    conversation_ref: canonicalRef,
    created_at: 1,
    last_updated_at: 2,
    is_running: false,
    messages: [
      {
        id: "assistant-uuid-1",
        role: "assistant",
        timestamp: 1,
        blocks: [],
      },
    ],
    plans: [
      {
        id: "plan-7",
        slug: "plan-7",
        title: "Plan 7",
        preview: "Preview",
        content: "Content",
        provider: "claude",
        timestamp: 1,
        session_id: sessionId,
        project_path: projectPath,
        conversation_ref: canonicalRef,
      },
    ],
    total_usage: {
      input_tokens: 0,
      output_tokens: 0,
    },
    start_time: 1,
    end_time: 2,
    subagents: [
      {
        agent_id: "agent-1",
        has_file: true,
        project_path: projectPath,
        session_id: "claude-agent-1",
        conversation_ref: "agent-thread--claude-claude-agent-1",
      },
    ],
    context_analytics: {
      buckets: [],
      steps: [],
    },
    context_window: {
      peak_context_window: 0,
      api_calls: 0,
      cumulative_tokens: 0,
    },
    ...overrides,
  };
}

function makeChildResolution(overrides: Partial<Record<string, unknown>> = {}) {
  return makeResolution({
    conversation_ref: "agent-thread--claude-claude-agent-1",
    route_slug: "agent-thread",
    session_id: "claude-agent-1",
    thread_type: "subagent",
    parent_session_id: sessionId,
    ...overrides,
  });
}

function makeChildConversationDetail(overrides: Partial<Record<string, unknown>> = {}) {
  return makeConversationDetail({
    session_id: "claude-agent-1",
    conversation_ref: "agent-thread--claude-claude-agent-1",
    thread_type: "subagent",
    ...overrides,
  });
}

function createTestDependencies(
  handlers: Record<string, { status?: number; body?: unknown }>
): ConversationPageDependencies & { fetchCalls: FetchCall[] } {
  const fetchCalls: FetchCall[] = [];

  return {
    fetchCalls,
    async fetchJson<T>(path: string, init?: RequestInit) {
      fetchCalls.push({ path, init });
      const response = handlers[path];
      if (!response) {
        throw new Error(`Unexpected fetch: ${path}`);
      }
      if ((response.status ?? 200) === 404) {
        return { status: 404, data: null };
      }
      return {
        status: response.status ?? 200,
        data: (response.body ?? null) as T | null,
      };
    },
    redirect(href) {
      throw new RedirectSignal(href);
    },
    notFound() {
      throw new NotFoundSignal();
    },
  };
}

class RedirectSignal extends Error {
  readonly href: string;

  constructor(href: string) {
    super(`redirect:${href}`);
    this.href = href;
  }
}

class NotFoundSignal extends Error {
  constructor() {
    super("not-found");
  }
}

test("canonical render paths resolve breadcrumbs, viewer locator, and entity ids", async () => {
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(canonicalRef)}`]: {
      body: makeResolution(),
    },
    [`/conversations/${encodeURIComponent(projectPath)}/${sessionId}`]: {
      body: makeConversationDetail(),
    },
  });

  const handlePage = createConversationPageHandler(deps);
  const result = await handlePage({
    segments: [canonicalRef, "plans", "plan-7"],
    searchParams: new URLSearchParams(),
  });

  assert.equal(result.kind, "render");
  assert.deepEqual(
    deps.fetchCalls.map((call) => call.path),
    [
      `/conversations/by-ref/${encodeURIComponent(canonicalRef)}`,
      `/conversations/${encodeURIComponent(projectPath)}/${sessionId}`,
    ]
  );
  assert.equal(result.viewer.projectPath, projectPath);
  assert.equal(result.viewer.sessionId, sessionId);
  assert.equal(result.viewer.conversationRef, canonicalRef);
  assert.equal(result.viewer.parentSessionId, undefined);
  assert.equal(result.viewer.initialTab, "plans");
  assert.equal(result.viewer.initialPlanId, "plan-7");
  assert.equal(result.breadcrumbs[1]?.title, projectPath);
  assert.equal(result.breadcrumbs[2]?.label, "claude-s...");
});

test("canonical tab routes render without nested detail validation", async () => {
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(canonicalRef)}`]: {
      body: makeResolution(),
    },
  });

  const handlePage = createConversationPageHandler(deps);
  const result = await handlePage({
    segments: [canonicalRef, "dag"],
    searchParams: new URLSearchParams(),
  });

  assert.equal(result.kind, "render");
  assert.equal(result.viewer.initialTab, "dag");
  assert.equal(result.viewer.initialMessageId, undefined);
  assert.equal(result.viewer.initialPlanId, undefined);
  assert.equal(result.viewer.initialSubagentId, undefined);
  assert.deepEqual(deps.fetchCalls.map((call) => call.path), [
    `/conversations/by-ref/${encodeURIComponent(canonicalRef)}`,
  ]);
});

test("OpenClaw canonical tab routes preserve the openclaw tab", async () => {
  const openClawRef =
    "review-openclaw-rollout--openclaw-openclaw:agent:main::openclaw-session-1";
  const openClawProjectPath = "openclaw:agent:main";
  const openClawSessionId = "openclaw-session-1";
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(openClawRef)}`]: {
      body: makeResolution({
        conversation_ref: openClawRef,
        route_slug: "review-openclaw-rollout",
        project_path: openClawProjectPath,
        session_id: openClawSessionId,
      }),
    },
    [`/conversations/${encodeURIComponent(openClawProjectPath)}/${openClawSessionId}`]: {
      body: makeConversationDetail({
        session_id: openClawSessionId,
        project_path: openClawProjectPath,
        provider: "openclaw",
        provider_detail: {
          kind: "openclaw",
          openclaw: {
            artifact_inventory: {},
          },
        },
      }),
    },
  });

  const handlePage = createConversationPageHandler(deps);
  const result = await handlePage({
    segments: [openClawRef, "openclaw"],
    searchParams: new URLSearchParams(),
  });

  assert.equal(result.kind, "render");
  assert.equal(result.viewer.initialTab, "openclaw");
  assert.deepEqual(
    deps.fetchCalls.map((call) => call.path),
    [
      `/conversations/by-ref/${encodeURIComponent(openClawRef)}`,
      `/conversations/${encodeURIComponent(openClawProjectPath)}/${openClawSessionId}`,
    ]
  );
});

test("child canonical routes fetch detail with parent_session_id and pass parentSessionId to the viewer", async () => {
  const childRef = "agent-thread--claude-claude-agent-1";
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(childRef)}`]: {
      body: makeChildResolution(),
    },
  });

  const handlePage = createConversationPageHandler(deps);
  const result = await handlePage({
    segments: [childRef, "messages"],
    searchParams: new URLSearchParams(),
  });

  assert.equal(result.kind, "render");
  assert.deepEqual(
    deps.fetchCalls.map((call) => call.path),
    [`/conversations/by-ref/${encodeURIComponent(childRef)}`]
  );
  assert.equal(result.viewer.sessionId, "claude-agent-1");
  assert.equal(result.viewer.parentSessionId, sessionId);
});

test("canonical base routes redirect to /messages", async () => {
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(canonicalRef)}`]: {
      body: makeResolution(),
    },
  });

  const handlePage = createConversationPageHandler(deps);

  await assert.rejects(
    handlePage({
      segments: [canonicalRef],
      searchParams: new URLSearchParams(),
    }),
    (error: unknown) =>
      error instanceof RedirectSignal &&
      error.href === `/conversations/${canonicalRef}/messages`
  );
});

test("wrong-slug canonical paths redirect to the resolver canonical ref", async () => {
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(wrongSlugRef)}`]: {
      body: makeResolution(),
    },
  });

  const handlePage = createConversationPageHandler(deps);

  await assert.rejects(
    handlePage({
      segments: [wrongSlugRef, "messages", "assistant-uuid-1"],
      searchParams: new URLSearchParams(),
    }),
    (error: unknown) =>
      error instanceof RedirectSignal &&
      error.href === `/conversations/${canonicalRef}/messages/assistant-uuid-1`
  );
});

test("resolver 404 for well-formed canonical refs triggers notFound", async () => {
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(canonicalRef)}`]: {
      status: 404,
    },
  });

  const handlePage = createConversationPageHandler(deps);

  await assert.rejects(
    handlePage({
      segments: [canonicalRef, "messages"],
      searchParams: new URLSearchParams(),
    }),
    (error: unknown) => error instanceof NotFoundSignal
  );
});

test("legacy routes redirect through the resolved canonical ref", async () => {
  const deps = createTestDependencies({
    [`/conversations/${encodeURIComponent(projectPath)}/${sessionId}`]: {
      body: makeConversationDetail(),
    },
  });

  const handlePage = createConversationPageHandler(deps);

  await assert.rejects(
    handlePage({
      segments: [projectPath, sessionId],
      searchParams: new URLSearchParams("tab=subagents&subagent=agent-1"),
    }),
    (error: unknown) =>
      error instanceof RedirectSignal &&
      error.href === `/conversations/${canonicalRef}/subagents/agent-1`
  );
});

test("invalid canonical shapes trigger notFound before any backend fetch", async () => {
  const deps = createTestDependencies({});
  const handlePage = createConversationPageHandler(deps);

  await assert.rejects(
    handlePage({
      segments: [canonicalRef, "unknown", "extra"],
      searchParams: new URLSearchParams(),
    }),
    (error: unknown) => error instanceof NotFoundSignal
  );

  assert.equal(deps.fetchCalls.length, 0);
});

test("invalid nested canonical entities trigger notFound after detail fetch", async () => {
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(canonicalRef)}`]: {
      body: makeResolution(),
    },
    [`/conversations/${encodeURIComponent(projectPath)}/${sessionId}`]: {
      body: makeConversationDetail(),
    },
  });

  const handlePage = createConversationPageHandler(deps);

  await assert.rejects(
    handlePage({
      segments: [canonicalRef, "subagents", "missing-agent"],
      searchParams: new URLSearchParams(),
    }),
    (error: unknown) => error instanceof NotFoundSignal
  );

  assert.deepEqual(
    deps.fetchCalls.map((call) => call.path),
    [
      `/conversations/by-ref/${encodeURIComponent(canonicalRef)}`,
      `/conversations/${encodeURIComponent(projectPath)}/${sessionId}`,
    ]
  );
});

test("child-thread canonical routes use the resolved parent session for detail fetches", async () => {
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(canonicalRef)}`]: {
      body: makeResolution({
        thread_type: "subagent",
        parent_session_id: "parent-session-1",
      }),
    },
    [`/conversations/${encodeURIComponent(projectPath)}/${sessionId}?parent_session_id=parent-session-1`]:
      {
        body: makeConversationDetail(),
      },
  });

  const handlePage = createConversationPageHandler(deps);
  const result = await handlePage({
    segments: [canonicalRef, "messages", "assistant-uuid-1"],
    searchParams: new URLSearchParams(),
  });

  assert.equal(result.kind, "render");
  assert.equal(result.viewer.parentSessionId, "parent-session-1");
  assert.deepEqual(
    deps.fetchCalls.map((call) => call.path),
    [
      `/conversations/by-ref/${encodeURIComponent(canonicalRef)}`,
      `/conversations/${encodeURIComponent(projectPath)}/${sessionId}?parent_session_id=parent-session-1`,
    ]
  );
});

test("provider filters render an OpenClaw option", () => {
  const markup = renderToStaticMarkup(
    React.createElement(ProviderFilter, {
      value: "openclaw",
      onChange: () => {},
    })
  );

  assert.equal(
    providerFilterOptions.some((option) => option.value === "openclaw"),
    true
  );
  assert.match(markup, /OpenClaw/);
});

test("OpenClaw conversation payloads are not mislabeled as Claude or Codex", () => {
  assert.equal(resolveConversationProvider("openclaw:agent:main"), "openclaw");
  assert.equal(resolveConversationProvider("openclaw:agent:main", "openclaw"), "openclaw");
  assert.equal(conversationProviderLabel("openclaw"), "OpenClaw");
});

test("conversation load errors are only fatal when no conversation data is available", () => {
  assert.equal(hasFatalConversationLoadError(undefined, undefined), true);
  assert.equal(hasFatalConversationLoadError(undefined, new Error("boom")), true);
  assert.equal(
    hasFatalConversationLoadError({ sessionId: "session-1" } as { sessionId: string }, undefined),
    false
  );
  assert.equal(
    hasFatalConversationLoadError(
      { sessionId: "session-1" } as { sessionId: string },
      new Error("transient poll failure")
    ),
    false
  );
});

test("project provider filtering does not treat every non-codex namespace as Claude", () => {
  const openClawConversation = {
    projectPath: "openclaw:agent:main",
    provider: "openclaw" as const,
  };

  assert.equal(matchesConversationProvider(openClawConversation, "all"), true);
  assert.equal(matchesConversationProvider(openClawConversation, "openclaw"), true);
  assert.equal(matchesConversationProvider(openClawConversation, "claude"), false);
  assert.equal(matchesConversationProvider(openClawConversation, "codex"), false);
});

test("route parsing accepts the OpenClaw provider detail tab", () => {
  assert.equal(resolveConversationDetailTab("openclaw"), "openclaw");
});

test("non-OpenClaw conversations reject the provider-specific openclaw tab", async () => {
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(canonicalRef)}`]: {
      body: makeResolution(),
    },
    [`/conversations/${encodeURIComponent(projectPath)}/${sessionId}`]: {
      body: makeConversationDetail({
        provider: "claude",
      }),
    },
  });

  const handlePage = createConversationPageHandler(deps);

  await assert.rejects(
    handlePage({
      segments: [canonicalRef, "openclaw"],
      searchParams: new URLSearchParams(),
    }),
    (error: unknown) => error instanceof NotFoundSignal
  );
});

test("OpenClaw conversations still resolve into the raw conversation view", async () => {
  const openClawRef = "review-openclaw-rollout--openclaw-openclaw-session-1";
  const openClawProjectPath = "openclaw:agent:main";
  const openClawSessionId = "openclaw-session-1";
  const deps = createTestDependencies({
    [`/conversations/by-ref/${encodeURIComponent(openClawRef)}`]: {
      body: makeResolution({
        conversation_ref: openClawRef,
        route_slug: "review-openclaw-rollout",
        project_path: openClawProjectPath,
        session_id: openClawSessionId,
      }),
    },
    [`/conversations/${encodeURIComponent(openClawProjectPath)}/${openClawSessionId}`]: {
      body: makeConversationDetail({
        session_id: openClawSessionId,
        project_path: openClawProjectPath,
        route_slug: "review-openclaw-rollout",
        conversation_ref: openClawRef,
        provider: "openclaw",
        model: "openclaw-v1",
        plans: [
          {
            id: "plan-openclaw-1",
            slug: "plan-openclaw-1",
            title: "OpenClaw plan",
            preview: "Preview",
            content: "Content",
            provider: "openclaw",
            timestamp: 1,
            session_id: openClawSessionId,
            project_path: openClawProjectPath,
            conversation_ref: openClawRef,
          },
        ],
      }),
    },
  });

  const handlePage = createConversationPageHandler(deps);
  const result = await handlePage({
    segments: [openClawRef, "messages", "assistant-uuid-1"],
    searchParams: new URLSearchParams(),
  });

  assert.equal(result.kind, "render");
  assert.equal(result.viewer.projectPath, openClawProjectPath);
  assert.equal(result.viewer.sessionId, openClawSessionId);
  assert.equal(result.viewer.conversationRef, openClawRef);
  assert.equal(result.viewer.initialTab, "messages");
  assert.deepEqual(
    deps.fetchCalls.map((call) => call.path),
    [
      `/conversations/by-ref/${encodeURIComponent(openClawRef)}`,
      `/conversations/${encodeURIComponent(openClawProjectPath)}/${openClawSessionId}`,
    ]
  );
});
