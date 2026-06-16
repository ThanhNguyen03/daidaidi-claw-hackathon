const FALLBACK_BACKEND_URL =
  'https://endpoint-3df85d3a-3888-4c44-b45a-17c3f85a60ef.agentbase-runtime.aiplatform.vngcloud.vn';

export function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL || FALLBACK_BACKEND_URL;
}
