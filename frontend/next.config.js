/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for Docker deployment
  output: 'standalone',
  // Enable experimental features if needed
  experimental: {
    // Enable server actions
    serverActions: {
      bodySizeLimit: "2mb",
    },
  },
  // Ensure proper handling of env vars
  env: {
    // These will be available client-side
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL ||
      "https://endpoint-3a16ebff-db7e-4961-bafc-6ae01f0bdd74.agentbase-runtime.aiplatform.vngcloud.vn",
  },
  // Images configuration for production
  images: {
    domains: ['localhost'],
  },
};

module.exports = nextConfig;
