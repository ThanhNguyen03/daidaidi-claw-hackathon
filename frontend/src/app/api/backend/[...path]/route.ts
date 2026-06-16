import { NextRequest } from 'next/server';

export const runtime = 'nodejs';

function getBackendBaseUrl() {
  return (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'https://endpoint-3a16ebff-db7e-4961-bafc-6ae01f0bdd74.agentbase-runtime.aiplatform.vngcloud.vn'
  );
}

async function proxyRequest(
  request: NextRequest,
  params: { path: string[] }
) {
  const backendBaseUrl = getBackendBaseUrl();
  const targetUrl = new URL(params.path.join('/'), `${backendBaseUrl.replace(/\/$/, '')}/`);
  targetUrl.search = request.nextUrl.search;

  const headers = new Headers(request.headers);
  headers.delete('host');

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: 'manual',
  };

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.arrayBuffer();
    // @ts-expect-error Node fetch accepts duplex for streamed request bodies.
    init.duplex = 'half';
  }

  const upstream = await fetch(targetUrl.toString(), init);

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete('content-encoding');
  responseHeaders.delete('transfer-encoding');
  responseHeaders.delete('connection');

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params);
}

export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params);
}

export async function PUT(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params);
}

export async function PATCH(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params);
}

export async function DELETE(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params);
}

export async function OPTIONS(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params);
}
