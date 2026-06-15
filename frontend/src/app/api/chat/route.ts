/**
 * Chat API Route (BFF)
 * =====================
 * Backend-for-Frontend route that proxies SSE to the FastAPI backend.
 * Keeps LLM_API_KEY server-side (per PLAN recommendation).
 */

import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function POST(request: NextRequest) {
  try {
    // Get the request body
    const body = await request.json();

    // Forward the request to the backend
    const response = await fetch(`${API_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend error: ${response.status}` },
        { status: response.status }
      );
    }

    // Create a streaming response
    const reader = response.body?.getReader();
    if (!reader) {
      return NextResponse.json({ error: 'Failed to read response stream' }, { status: 500 });
    }

    const stream = new ReadableStream({
      async start(controller) {
        const decoder = new TextDecoder();

        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              controller.close();
              break;
            }

            controller.enqueue(value);
          }
        } catch (error) {
          controller.error(error);
        }
      },
    });

    return new NextResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  } catch (error) {
    console.error('Chat API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

// Handle GET for health check or other methods
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const action = searchParams.get('action');

  if (action === 'health') {
    try {
      const response = await fetch(`${API_URL}/health`);
      const data = await response.json();
      return NextResponse.json(data);
    } catch {
      return NextResponse.json(
        { status: 'unhealthy', error: 'Backend unreachable' },
        { status: 503 }
      );
    }
  }

  return NextResponse.json({ error: 'Method not allowed' }, { status: 405 });
}
