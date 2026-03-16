import { mapEnvelopeToUILiveUpdate, getLiveEventsUrl, type LiveIngestionEnvelope } from "@/lib/live-events";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

interface ParsedSSEMessage {
  data: string;
  event: string;
  id?: string;
}

function parseSSEMessage(block: string): ParsedSSEMessage | null {
  const data: string[] = [];
  let event = "message";
  let id: string | undefined;

  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) {
      continue;
    }

    const separatorIndex = line.indexOf(":");
    const field = separatorIndex === -1 ? line : line.slice(0, separatorIndex);
    let value = separatorIndex === -1 ? "" : line.slice(separatorIndex + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }

    switch (field) {
      case "data":
        data.push(value);
        break;
      case "event":
        event = value || "message";
        break;
      case "id":
        id = value;
        break;
      default:
        break;
    }
  }

  if (data.length === 0) {
    return null;
  }

  return {
    data: data.join("\n"),
    event,
    id,
  };
}

function encodeSSEEvent(event: string, data: string, id?: string): Uint8Array {
  let chunk = "";
  if (id) {
    chunk += `id: ${id}\n`;
  }
  chunk += `event: ${event}\n`;
  for (const line of data.split("\n")) {
    chunk += `data: ${line}\n`;
  }
  chunk += "\n";
  return new TextEncoder().encode(chunk);
}

async function forwardEnvelopeEvents(
  upstream: ReadableStream<Uint8Array>,
  controller: ReadableStreamDefaultController<Uint8Array>
) {
  const reader = upstream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    controller.enqueue(new TextEncoder().encode("retry: 3000\n\n"));

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true }).replace(/\r/g, "");
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");

        const message = parseSSEMessage(block);
        if (!message || message.event !== "envelope") {
          continue;
        }

        try {
          const envelope = JSON.parse(message.data) as LiveIngestionEnvelope;
          const update = mapEnvelopeToUILiveUpdate(envelope);
          controller.enqueue(
            encodeSSEEvent("live-update", JSON.stringify(update), message.id ?? update.eventId)
          );
        } catch {
          // Ignore malformed upstream payloads and keep the polling fallback active.
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function GET(request: Request) {
  const headers = new Headers({
    Accept: "text/event-stream",
    "Cache-Control": "no-cache",
  });
  const lastEventId = request.headers.get("last-event-id");
  if (lastEventId) {
    headers.set("Last-Event-ID", lastEventId);
  }

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(getLiveEventsUrl(), {
      headers,
      cache: "no-store",
      signal: request.signal,
    });
  } catch {
    return new Response("Live event stream unavailable", { status: 503 });
  }

  if (!upstreamResponse.ok || !upstreamResponse.body) {
    return new Response("Live event stream unavailable", { status: 503 });
  }

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        await forwardEnvelopeEvents(upstreamResponse.body!, controller);
      } catch {
        if (request.signal.aborted) {
          controller.close();
          return;
        }
        controller.close();
        return;
      }
      controller.close();
    },
    cancel() {
      upstreamResponse.body?.cancel().catch(() => {});
    },
  });

  return new Response(stream, {
    headers: {
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "Content-Type": "text/event-stream",
      "X-Accel-Buffering": "no",
    },
  });
}
