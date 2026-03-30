type BackendJsonResponse<T> = {
  status: number;
  data: T | null;
};

export function getBackendBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }
  const fallbackPort = process.env.HELA_API_PORT?.trim() || "30000";
  return `http://127.0.0.1:${fallbackPort}`;
}

export async function fetchBackendJson<T>(
  path: string,
  init?: RequestInit
): Promise<BackendJsonResponse<T>> {
  const response = await fetch(`${getBackendBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      accept: "application/json",
      ...init?.headers,
    },
    next: {
      revalidate: 0,
      ...init?.next,
    },
  });

  if (response.status === 404) {
    return {
      status: 404,
      data: null,
    };
  }

  if (!response.ok) {
    throw new Error(`Backend request failed (${response.status}): ${path}`);
  }

  return {
    status: response.status,
    data: (await response.json()) as T,
  };
}
