/**
 * Shared fetch primitives used by SWR hooks and direct mutation call-sites.
 */

type Normalizer<T> = (value: unknown) => T;

function readErrorMessage(payload: unknown): string | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }

  const body = payload as Record<string, unknown>;

  if (typeof body.error === "string" && body.error.trim()) {
    return body.error;
  }

  if (typeof body.detail === "string" && body.detail.trim()) {
    return body.detail;
  }

  if (Array.isArray(body.detail) && body.detail.length > 0) {
    const first = body.detail[0];
    if (typeof first === "string" && first.trim()) {
      return first;
    }

    if (typeof first === "object" && first !== null) {
      const message = (first as Record<string, unknown>).msg;
      if (typeof message === "string" && message.trim()) {
        return message;
      }
    }
  }

  return null;
}

export async function requestJson<T>(
  url: string,
  init?: RequestInit,
  normalize?: Normalizer<T>
): Promise<T> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => null);

  if (!res.ok) {
    throw new Error(readErrorMessage(body) ?? `Request failed with status ${res.status}.`);
  }

  if (normalize) {
    return normalize(body);
  }

  return body as T;
}

export const fetcher = (url: string) => requestJson(url);

// ---------------------------------------------------------------------------
// Mutation helpers
// ---------------------------------------------------------------------------

export function post<T = unknown>(
  url: string,
  body?: unknown,
  normalize?: Normalizer<T>
): Promise<T> {
  return requestJson<T>(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    },
    normalize
  );
}

export function patch<T = unknown>(
  url: string,
  body: unknown,
  normalize?: Normalizer<T>
): Promise<T> {
  return requestJson<T>(
    url,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    normalize
  );
}

export function del<T = unknown>(url: string, normalize?: Normalizer<T>): Promise<T> {
  return requestJson<T>(url, { method: "DELETE" }, normalize);
}
