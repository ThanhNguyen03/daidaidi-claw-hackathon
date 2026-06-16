# =============================================================================
# Frontend Dockerfile for AgentBase Runtime Deployment
# =============================================================================
# Multi-stage build for production-optimized image
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

ARG NEXT_PUBLIC_API_URL=https://endpoint-3a16ebff-db7e-4961-bafc-6ae01f0bdd74.agentbase-runtime.aiplatform.vngcloud.vn
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production image
FROM node:18-alpine AS runner

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Set working directory
WORKDIR /app

ARG NEXT_PUBLIC_API_URL=https://endpoint-3a16ebff-db7e-4961-bafc-6ae01f0bdd74.agentbase-runtime.aiplatform.vngcloud.vn
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Copy built artifacts
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Set environment
ENV PORT=8080
ENV NODE_ENV production

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:8080/health || exit 1

# Change ownership
RUN chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

# Run the application
CMD ["node", "server.js"]
