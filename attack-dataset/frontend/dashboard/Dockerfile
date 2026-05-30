# ── Production Dockerfile for Dashboard ────────────────────────────────────────────
# Multi-stage build for optimized production image

# ── Stage 1: Dependencies Builder ───────────────────────────────────────────────
FROM node:20-alpine as deps

RUN apk add --no-cache libc6-compat

WORKDIR /app

COPY package.json package-lock.json* ./

RUN npm ci && \
    npm cache clean --force

# ── Stage 2: Builder ───────────────────────────────────────────────────────────────
FROM node:20-alpine as builder

RUN apk add --no-cache libc6-compat

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:3001
ARG NEXT_PUBLIC_ANALYZER_URL=http://localhost:8001
ARG NEXT_PUBLIC_KNOWLEDGE_ENGINE_URL=http://localhost:8000
ARG NEXT_PUBLIC_OPSEC_URL=http://localhost:8002

# Set environment variables for build
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    NEXT_PUBLIC_ORCHESTRATOR_URL=$NEXT_PUBLIC_ORCHESTRATOR_URL \
    NEXT_PUBLIC_ANALYZER_URL=$NEXT_PUBLIC_ANALYZER_URL \
    NEXT_PUBLIC_KNOWLEDGE_ENGINE_URL=$NEXT_PUBLIC_KNOWLEDGE_ENGINE_URL \
    NEXT_PUBLIC_OPSEC_URL=$NEXT_PUBLIC_OPSEC_URL

# Build application
RUN npm run build

# ── Stage 3: Production Runtime ─────────────────────────────────────────────────
FROM node:20-alpine as runner

RUN apk add --no-cache \
    curl \
    dumb-init

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy necessary files from builder
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]

# Start the application
CMD ["node", "server.js"]