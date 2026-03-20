/**
 * Shared fetch primitives used by SWR hooks and direct mutation call-sites.
 */

import type { ZodType } from "zod";

type Normalizer<TInput, TOutput = TInput> = (value: TInput) => TOutput;
type Schema<T> = ZodType<T>;
const MAX_VALIDATION_ISSUES = 3;

function isSchema<T>(value: unknown): value is Schema<T> {
  return typeof value === "object" && value !== null && "safeParse" in value;
}

function sanitizeUrlForError(url: string): string {
  try {
    const parsed = new URL(url);
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return url.split("?")[0] ?? url;
  }
}

function formatValidationError(url: string, issues: Array<{ path: PropertyKey[]; message: string }>) {
  const visibleIssues = issues.slice(0, MAX_VALIDATION_ISSUES);
  const hiddenCount = Math.max(issues.length - visibleIssues.length, 0);
  const summary = visibleIssues
    .map((issue) => {
      const path = issue.path.length > 0 ? issue.path.join(".") : "<root>";
      return `${path}: ${issue.message}`;
    })
    .join("; ");
  const suffix = hiddenCount > 0 ? `; ${hiddenCount} more issue(s)` : "";

  return `Response validation failed for ${sanitizeUrlForError(url)}: ${summary}${suffix}`;
}

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
  normalize?: Normalizer<unknown, T>
): Promise<T>;

export async function requestJson<T>(
  url: string,
  init: RequestInit | undefined,
  schema: Schema<T>
): Promise<T>;

export async function requestJson<TSchema, TOutput>(
  url: string,
  init: RequestInit | undefined,
  schema: Schema<TSchema> | undefined,
  normalize: Normalizer<TSchema, TOutput>
): Promise<TOutput>;

export async function requestJson(
  url: string,
  init?: RequestInit,
  schemaOrNormalize?: Schema<unknown> | Normalizer<unknown>,
  normalize?: Normalizer<unknown>
): Promise<unknown> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => null);

  if (!res.ok) {
    throw new Error(readErrorMessage(body) ?? `Request failed with status ${res.status}.`);
  }

  const schema = isSchema<unknown>(schemaOrNormalize) ? schemaOrNormalize : undefined;
  const legacyNormalize =
    typeof schemaOrNormalize === "function" ? schemaOrNormalize : undefined;
  if (schema) {
    const parsedBody = schema.safeParse(body);
    if (!parsedBody.success) {
      throw new Error(formatValidationError(url, parsedBody.error.issues));
    }

    if (normalize) {
      return normalize(parsedBody.data);
    }

    return parsedBody.data;
  }

  if (legacyNormalize) {
    return legacyNormalize(body);
  }

  return body;
}

export const fetcher = (url: string) => requestJson(url);

// ---------------------------------------------------------------------------
// Mutation helpers
// ---------------------------------------------------------------------------

export function post<T = unknown>(
  url: string,
  body?: unknown,
  normalize?: Normalizer<unknown, T>
): Promise<T>;

export function post<T>(
  url: string,
  body: unknown,
  schema: Schema<T>
): Promise<T>;

export function post<TSchema, TOutput>(
  url: string,
  body: unknown,
  schema: Schema<TSchema> | undefined,
  normalize: Normalizer<TSchema, TOutput>
): Promise<TOutput>;

export function post(
  url: string,
  body?: unknown,
  schemaOrNormalize?: Schema<unknown> | Normalizer<unknown>,
  normalize?: Normalizer<unknown>
): Promise<unknown> {
  const init = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  if (typeof schemaOrNormalize === "function") {
    return requestJson(url, init, schemaOrNormalize);
  }

  if (schemaOrNormalize) {
    return normalize
      ? requestJson(url, init, schemaOrNormalize, normalize)
      : requestJson(url, init, schemaOrNormalize);
  }

  return requestJson(url, init);
}

export function patch<T = unknown>(
  url: string,
  body: unknown,
  normalize?: Normalizer<unknown, T>
): Promise<T>;

export function patch<T>(
  url: string,
  body: unknown,
  schema: Schema<T>
): Promise<T>;

export function patch<TSchema, TOutput>(
  url: string,
  body: unknown,
  schema: Schema<TSchema> | undefined,
  normalize: Normalizer<TSchema, TOutput>
): Promise<TOutput>;

export function patch(
  url: string,
  body: unknown,
  schemaOrNormalize?: Schema<unknown> | Normalizer<unknown>,
  normalize?: Normalizer<unknown>
): Promise<unknown> {
  const init = {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };

  if (typeof schemaOrNormalize === "function") {
    return requestJson(url, init, schemaOrNormalize);
  }

  if (schemaOrNormalize) {
    return normalize
      ? requestJson(url, init, schemaOrNormalize, normalize)
      : requestJson(url, init, schemaOrNormalize);
  }

  return requestJson(url, init);
}

export function del<T = unknown>(url: string, normalize?: Normalizer<unknown, T>): Promise<T>;

export function del<T>(url: string, schema: Schema<T>): Promise<T>;

export function del<TSchema, TOutput>(
  url: string,
  schema: Schema<TSchema> | undefined,
  normalize: Normalizer<TSchema, TOutput>
): Promise<TOutput>;

export function del(
  url: string,
  schemaOrNormalize?: Schema<unknown> | Normalizer<unknown>,
  normalize?: Normalizer<unknown>
): Promise<unknown> {
  const init = { method: "DELETE" };

  if (typeof schemaOrNormalize === "function") {
    return requestJson(url, init, schemaOrNormalize);
  }

  if (schemaOrNormalize) {
    return normalize
      ? requestJson(url, init, schemaOrNormalize, normalize)
      : requestJson(url, init, schemaOrNormalize);
  }

  return requestJson(url, init);
}
