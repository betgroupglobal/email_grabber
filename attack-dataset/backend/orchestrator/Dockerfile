# ── Production Dockerfile for Orchestrator ────────────────────────────────────────
# Multi-stage build for optimized production image

# ── Stage 1: Base Builder ───────────────────────────────────────────────────────
FROM node:20-alpine as base-builder

# Set environment variables
ENV NODE_ENV=production \
    NODE_OPTIONS="--max-old-space-size=4096"

# Install build dependencies
RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    curl

# ── Stage 2: Dependencies Builder ─────────────────────────────────────────────
FROM base-builder as dependencies-builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production && \
    npm cache clean --force

# ── Stage 3: Application Builder ───────────────────────────────────────────────
FROM dependencies-builder as app-builder

WORKDIR /app

# Copy application code
COPY . .

# Build application if needed
RUN npm run build || true

# ── Stage 4: Production Runtime ─────────────────────────────────────────────────
FROM node:20-alpine as production

# Install runtime dependencies
RUN apk add --no-cache \
    curl \
    dumb-init

# Set environment variables
ENV NODE_ENV=production \
    NODE_OPTIONS="--max-old-space-size=4096" \
    LIVE_COUNCIL_DEFAULT=true \
    LIVE_MAX_REPLANS=5 \
    LIVE_REPLAN_TOP_CHAINS=2
    
WORKDIR /app

# Copy dependencies from builder stage
COPY --from=dependencies-builder /app/node_modules /app/node_modules
COPY --from=app-builder /app /app

# Create logs directory
RUN mkdir -p /app/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:3001/health || exit 1

# Expose port
EXPOSE 3001

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]

# Run with cluster mode for production
CMD ["node", "index.js"]