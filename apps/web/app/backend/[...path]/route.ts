import { NextRequest } from "next/server";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyToApi(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyToApi(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyToApi(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyToApi(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyToApi(request, context);
}

async function proxyToApi(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const sourceUrl = new URL(request.url);
  const targetUrl = `${apiBaseUrl}/api/${path.join("/")}${sourceUrl.search}`;
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");
  headers.delete("connection");
  headers.delete("expect");
  headers.delete("keep-alive");
  headers.delete("proxy-authenticate");
  headers.delete("proxy-authorization");
  headers.delete("te");
  headers.delete("trailer");
  headers.delete("transfer-encoding");
  headers.delete("upgrade");

  const init: RequestInit & { duplex?: "half" } = {
    headers,
    method: request.method,
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
    init.duplex = "half";
  }

  const response = await fetch(targetUrl, init);
  return new Response(response.body, {
    headers: response.headers,
    status: response.status,
    statusText: response.statusText,
  });
}
