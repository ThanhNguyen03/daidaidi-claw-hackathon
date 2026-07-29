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
      "http://localhost:8000",
  },
  // Images configuration for production
  images: {
    domains: ['localhost'],
  },
  // next@14.2.35's own bundled lint step calls ESLint's legacy Node API, which
  // eslint-config-next 16 / ESLint 9 removed — it now errors out harmlessly on
  // every build. `npm run lint` (plain `eslint .` + eslint.config.mjs) is the
  // real lint check; skip Next's redundant, broken one during builds.
  eslint: {
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
