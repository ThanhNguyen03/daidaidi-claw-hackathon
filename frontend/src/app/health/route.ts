/**
 * Health Check Route
 * ==================
 * Provides a health check endpoint for container orchestration.
 * This is required for proper container health checks.
 */

import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
  });
}