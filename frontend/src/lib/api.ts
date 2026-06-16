const FALLBACK_BACKEND_URL =
  'https://endpoint-3a16ebff-db7e-4961-bafc-6ae01f0bdd74.agentbase-runtime.aiplatform.vngcloud.vn';

export function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL || FALLBACK_BACKEND_URL;
}
