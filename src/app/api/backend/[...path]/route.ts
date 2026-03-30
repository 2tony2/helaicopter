import { getBackendBaseUrl } from "@/lib/server/backend-api";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

export const dynamic = "force-dynamic";
export const revalidate = 0;

function buildTargetUrl(requestUrl: string, path: string[]) {
  const target = new URL(getBackendBaseUrl());
  const pathname = path.map((segment) => encodeURIComponent(segment)).join("/");
  target.pathname = `${target.pathname.replace(/\/+$/, "")}/${pathname}`;
  target.search = new URL(requestUrl).search;
  return target;
}

async function proxyRequest(request: Request, context: RouteContext) {
  const { path = [] } = await context.params;
  const target = buildTargetUrl(request.url, path);
  const headers = new Headers(request.headers);

  headers.delete("host");

  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    cache: "no-store",
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
    init.duplex = "half";
  }

  const response = await fetch(target, init);
  const responseHeaders = new Headers(response.headers);

  responseHeaders.delete("transfer-encoding");

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function POST(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PUT(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PATCH(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function DELETE(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function OPTIONS(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}
