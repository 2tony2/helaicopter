export interface LiveIngestionEnvelope {
  provider: string;
  conversationId: string;
  sessionId: string;
  sourcePath: string;
  sourceLine: number;
  eventId: string;
  eventType: string;
  eventTime: string;
  projectPath: string;
  projectName: string;
}

export interface AnalyticsInvalidationEvent {
  kind: "analytics.invalidate";
  provider: string;
  eventType: string;
  eventTime: string;
}

export interface ConversationUpdateEvent {
  kind: "conversation.update";
  provider: string;
  conversationId: string;
  sessionId: string;
  projectPath: string;
  projectName: string;
  eventType: string;
  eventTime: string;
}

export interface UILiveUpdateEvent {
  type: "live.update";
  eventId: string;
  analytics: AnalyticsInvalidationEvent;
  conversation: ConversationUpdateEvent;
}

export function mapEnvelopeToUILiveUpdate(
  envelope: LiveIngestionEnvelope
): UILiveUpdateEvent {
  return {
    type: "live.update",
    eventId: envelope.eventId,
    analytics: {
      kind: "analytics.invalidate",
      provider: envelope.provider,
      eventType: envelope.eventType,
      eventTime: envelope.eventTime,
    },
    conversation: {
      kind: "conversation.update",
      provider: envelope.provider,
      conversationId: envelope.conversationId,
      sessionId: envelope.sessionId,
      projectPath: envelope.projectPath,
      projectName: envelope.projectName,
      eventType: envelope.eventType,
      eventTime: envelope.eventTime,
    },
  };
}

export function getLiveEventsUrl(): string {
  const explicitUrl =
    process.env.HELAICOPTER_GO_INGEST_EVENTS_URL ??
    process.env.HELAICOPTER_LIVE_EVENTS_URL;
  if (explicitUrl) {
    return explicitUrl;
  }

  const configuredAddr = process.env.HELAICOPTER_GO_INGEST_HTTP_ADDR ?? "127.0.0.1:4318";
  const baseUrl = configuredAddr.startsWith("http://") || configuredAddr.startsWith("https://")
    ? configuredAddr
    : `http://${configuredAddr}`;

  return `${baseUrl.replace(/\/+$/, "")}/events`;
}
