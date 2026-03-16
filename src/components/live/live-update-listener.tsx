"use client";

import { useEffect, useEffectEvent, useRef } from "react";
import { usePathname } from "next/navigation";
import { useSWRConfig } from "swr";
import type { UILiveUpdateEvent } from "@/lib/live-events";

interface ActiveConversationRoute {
  projectPath: string;
  sessionId: string;
}

interface PendingInvalidations {
  analytics: boolean;
  conversationLists: boolean;
  activeConversation: ActiveConversationRoute | null;
}

function readPathnameFromKey(key: unknown): string | null {
  if (typeof key !== "string") {
    return null;
  }

  try {
    return new URL(key, "http://localhost").pathname;
  } catch {
    return null;
  }
}

function parseActiveConversationRoute(pathname: string): ActiveConversationRoute | null {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length !== 3 || segments[0] !== "conversations") {
    return null;
  }

  const encodedProjectPath = segments[1];
  const sessionId = segments[2];
  if (!encodedProjectPath || !sessionId) {
    return null;
  }

  return {
    projectPath: decodeURIComponent(encodedProjectPath),
    sessionId,
  };
}

export function LiveUpdateListener() {
  const pathname = usePathname();
  const { mutate } = useSWRConfig();
  const flushTimeoutRef = useRef<number | null>(null);
  const pendingRef = useRef<PendingInvalidations>({
    analytics: false,
    conversationLists: false,
    activeConversation: null,
  });

  const flushPending = useEffectEvent(() => {
    const pending = pendingRef.current;
    pendingRef.current = {
      analytics: false,
      conversationLists: false,
      activeConversation: null,
    };

    if (pending.analytics) {
      void mutate(
        (key) => readPathnameFromKey(key) === "/api/analytics",
        undefined,
        { revalidate: true }
      );
    }

    if (pending.conversationLists) {
      void mutate(
        (key) => readPathnameFromKey(key) === "/api/conversations",
        undefined,
        { revalidate: true }
      );
    }

    if (!pending.activeConversation) {
      return;
    }

    const encodedProjectPath = encodeURIComponent(pending.activeConversation.projectPath);
    const detailKey = `/api/conversations/${encodedProjectPath}/${pending.activeConversation.sessionId}`;
    const tasksKey = `/api/tasks/${pending.activeConversation.sessionId}`;
    const subagentPrefix = `/api/subagents/${encodedProjectPath}/${pending.activeConversation.sessionId}/`;

    void mutate(detailKey, undefined, { revalidate: true });
    void mutate(tasksKey, undefined, { revalidate: true });
    void mutate(
      (key) => {
        const keyPathname = readPathnameFromKey(key);
        return keyPathname ? keyPathname.startsWith(subagentPrefix) : false;
      },
      undefined,
      { revalidate: true }
    );
  });

  const scheduleFlush = useEffectEvent(() => {
    if (flushTimeoutRef.current !== null) {
      return;
    }

    flushTimeoutRef.current = window.setTimeout(() => {
      flushTimeoutRef.current = null;
      flushPending();
    }, 500);
  });

  const queueUpdate = useEffectEvent((event: UILiveUpdateEvent) => {
    const pending = pendingRef.current;

    pending.analytics = pending.analytics || Boolean(event.analytics);
    pending.conversationLists = pending.conversationLists || Boolean(event.conversation);

    if (event.conversation) {
      const activeConversation = parseActiveConversationRoute(pathname);
      if (
        activeConversation &&
        activeConversation.projectPath === event.conversation.projectPath &&
        activeConversation.sessionId === event.conversation.sessionId
      ) {
        pending.activeConversation = activeConversation;
      }
    }

    scheduleFlush();
  });

  useEffect(() => {
    const source = new EventSource("/api/live-events");

    const handleUpdate = (event: MessageEvent<string>) => {
      try {
        queueUpdate(JSON.parse(event.data) as UILiveUpdateEvent);
      } catch {
        // Ignore malformed stream frames and fall back to polling.
      }
    };

    source.addEventListener("live-update", handleUpdate as EventListener);

    return () => {
      source.removeEventListener("live-update", handleUpdate as EventListener);
      source.close();
      if (flushTimeoutRef.current !== null) {
        window.clearTimeout(flushTimeoutRef.current);
        flushTimeoutRef.current = null;
      }
    };
  }, []);

  return null;
}
