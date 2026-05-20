"use strict";

/**
 * AutonomAI Orchestrator — Robustness Middleware
 *
 * Provides structured logging, request correlation, timeouts, metrics,
 * security headers, global error handling, and graceful shutdown.
 */

const { v4: uuidv4 } = require("uuid");

// ── Structured Logger ─────────────────────────────────────────────────────────

const LOG_LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3, FATAL: 4 };
const CURRENT_LOG_LEVEL = LOG_LEVELS[process.env.LOG_LEVEL?.toUpperCase()] ?? LOG_LEVELS.INFO;

class StructuredLogger {
  constructor(serviceName = "orchestrator") {
    this.serviceName = serviceName;
  }

  _log(level, message, meta = {}) {
    const levelValue = LOG_LEVELS[level] ?? LOG_LEVELS.INFO;
    if (levelValue < CURRENT_LOG_LEVEL) return;

    const entry = {
      timestamp: new Date().toISOString(),
      level,
      service: this.serviceName,
      message,
      ...meta,
    };

    // Output to stderr for ERROR/FATAL, stdout for others
    const output = levelValue >= LOG_LEVELS.ERROR ? process.stderr : process.stdout;
    output.write(JSON.stringify(entry) + "\n");
  }

  debug(msg, meta) { this._log("DEBUG", msg, meta); }
  info(msg, meta) { this._log("INFO", msg, meta); }
  warn(msg, meta) { this._log("WARN", msg, meta); }
  error(msg, meta) { this._log("ERROR", msg, meta); }
  fatal(msg, meta) { this._log("FATAL", msg, meta); }
}

const logger = new StructuredLogger();

// ── Request Correlation ───────────────────────────────────────────────────────

function correlationMiddleware(req, res, next) {
  req.correlationId = req.headers["x-correlation-id"] || uuidv4();
  req.requestStartTime = Date.now();

  // Add correlation ID to response headers
  res.setHeader("X-Correlation-ID", req.correlationId);
  res.setHeader("X-Request-ID", req.correlationId);

  // Inject logger into request
  req.logger = {
    debug: (msg, meta) => logger.debug(msg, { correlationId: req.correlationId, ...meta }),
    info: (msg, meta) => logger.info(msg, { correlationId: req.correlationId, ...meta }),
    warn: (msg, meta) => logger.warn(msg, { correlationId: req.correlationId, ...meta }),
    error: (msg, meta) => logger.error(msg, { correlationId: req.correlationId, ...meta }),
  };

  next();
}

// ── Request Logging ────────────────────────────────────────────────────────────

function requestLoggingMiddleware(req, res, next) {
  const start = Date.now();

  res.on("finish", () => {
    const duration = Date.now() - start;
    const logData = {
      correlationId: req.correlationId,
      method: req.method,
      path: req.path || req.url,
      statusCode: res.statusCode,
      durationMs: duration,
      contentLength: res.getHeader("content-length"),
      userAgent: req.headers["user-agent"],
      clientIp: req.headers["x-forwarded-for"] || req.socket?.remoteAddress,
    };

    if (res.statusCode >= 500) {
      req.logger.error("Request completed with server error", logData);
    } else if (res.statusCode >= 400) {
      req.logger.warn("Request completed with client error", logData);
    } else {
      req.logger.info("Request completed", logData);
    }
  });

  next();
}

// ── Request Timeout ─────────────────────────────────────────────────────────────

const DEFAULT_REQUEST_TIMEOUT_MS = parseInt(process.env.REQUEST_TIMEOUT_MS || "30000", 10);

const DEFAULT_LONG_RUNNING_TIMEOUT_MS = parseInt(
  process.env.AI_REQUEST_TIMEOUT_MS || "120000",
  10
);

/** @param {number} timeoutMs default request timeout */
/** @param {{ longRunningPaths?: string[], longRunningTimeoutMs?: number }} [opts] */
function timeoutMiddleware(timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, opts = {}) {
  const longRunningPaths = opts.longRunningPaths || [];
  const longRunningTimeoutMs = opts.longRunningTimeoutMs || DEFAULT_LONG_RUNNING_TIMEOUT_MS;

  return (req, res, next) => {
    const path = (req.path || req.url || "").split("?")[0];
    const isLongRunning = longRunningPaths.some(
      (prefix) => path === prefix || path.startsWith(`${prefix}/`)
    );
    const effectiveTimeoutMs = isLongRunning ? longRunningTimeoutMs : timeoutMs;

    req.setTimeout(effectiveTimeoutMs, () => {
      req.logger.error("Request timeout", {
        timeoutMs: effectiveTimeoutMs,
        path: req.path,
        longRunning: isLongRunning,
      });
      if (!res.headersSent) {
        res.status(504).json({
          error: {
            code: "GATEWAY_TIMEOUT",
            message: `Request timed out after ${effectiveTimeoutMs}ms`,
            details: { timeoutMs: effectiveTimeoutMs, path: req.path },
            timestamp: new Date().toISOString(),
          },
        });
      } else {
        res.end();
      }
    });

    next();
  };
}

// ── Metrics Collection ────────────────────────────────────────────────────────

class MetricsCollector {
  constructor() {
    this.requestCounts = new Map();
    this.errorCounts = new Map();
    this.responseTimeBuckets = new Map();
    this.activeRequests = 0;
    this.totalRequests = 0;
    this.startTime = Date.now();
  }

  recordRequest(method, path, statusCode, durationMs) {
    const key = `${method} ${path}`;
    this.requestCounts.set(key, (this.requestCounts.get(key) || 0) + 1);
    this.totalRequests++;

    if (statusCode >= 400) {
      const errorKey = `${statusCode}`;
      this.errorCounts.set(errorKey, (this.errorCounts.get(errorKey) || 0) + 1);
    }

    // Track response time buckets (in ms)
    const bucket = durationMs < 100 ? "<100ms"
      : durationMs < 250 ? "100-250ms"
      : durationMs < 500 ? "250-500ms"
      : durationMs < 1000 ? "500ms-1s"
      : durationMs < 2500 ? "1-2.5s"
      : durationMs < 5000 ? "2.5-5s"
      : durationMs < 10000 ? "5-10s"
      : ">10s";

    this.responseTimeBuckets.set(bucket, (this.responseTimeBuckets.get(bucket) || 0) + 1);
  }

  incrementActiveRequests() { this.activeRequests++; }
  decrementActiveRequests() { this.activeRequests = Math.max(0, this.activeRequests - 1); }

  getMetrics() {
    const uptime = Date.now() - this.startTime;
    return {
      uptime_seconds: Math.round(uptime / 1000),
      total_requests: this.totalRequests,
      active_requests: this.activeRequests,
      request_counts: Object.fromEntries(this.requestCounts),
      error_counts: Object.fromEntries(this.errorCounts),
      response_time_buckets: Object.fromEntries(this.responseTimeBuckets),
      timestamp: new Date().toISOString(),
    };
  }
}

const metricsCollector = new MetricsCollector();

function metricsMiddleware(req, res, next) {
  metricsCollector.incrementActiveRequests();
  const start = Date.now();

  res.on("finish", () => {
    metricsCollector.decrementActiveRequests();
    metricsCollector.recordRequest(req.method, req.route?.path || req.path, res.statusCode, Date.now() - start);
  });

  next();
}

function getMetricsEndpoint(req, res) {
  res.json(metricsCollector.getMetrics());
}

// ── Security Headers ────────────────────────────────────────────────────────────

function securityHeadersMiddleware(req, res, next) {
  // Prevent MIME type sniffing
  res.setHeader("X-Content-Type-Options", "nosniff");
  // Prevent clickjacking
  res.setHeader("X-Frame-Options", "DENY");
  // XSS protection
  res.setHeader("X-XSS-Protection", "1; mode=block");
  // Referrer policy
  res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
  // Content Security Policy (permissive for API)
  res.setHeader("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none';");
  // Permissions policy
  res.setHeader("Permissions-Policy", "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()");
  // Remove server fingerprinting
  res.removeHeader("X-Powered-By");

  next();
}

// ── Global Error Handling ───────────────────────────────────────────────────────

class AppError extends Error {
  constructor(message, statusCode = 500, code = "INTERNAL_SERVER_ERROR", details = {}) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    this.isOperational = true;
    Error.captureStackTrace(this, this.constructor);
  }
}

function globalErrorHandler(err, req, res, _next) {
  const correlationId = req?.correlationId || "unknown";

  // Determine status code and error code
  let statusCode = err.statusCode || err.status || 500;
  let errorCode = err.code || "INTERNAL_SERVER_ERROR";
  let message = err.message || "An unexpected error occurred";

  // Handle specific error types
  if (err.name === "SyntaxError" && err.type === "entity.parse.failed") {
    statusCode = 400;
    errorCode = "INVALID_JSON";
    message = "Invalid JSON in request body";
  } else if (err.name === "UnauthorizedError") {
    statusCode = 401;
    errorCode = "UNAUTHORIZED";
  } else if (err.code === "ECONNREFUSED" || err.code === "ETIMEDOUT") {
    statusCode = 503;
    errorCode = "SERVICE_UNAVAILABLE";
    message = "Dependency service unavailable";
  }

  // Log the error
  const logData = {
    correlationId,
    errorCode,
    statusCode,
    message: err.message,
    stack: process.env.NODE_ENV === "development" ? err.stack : undefined,
    path: req?.path,
    method: req?.method,
  };

  if (statusCode >= 500) {
    logger.error("Server error", logData);
  } else {
    logger.warn("Client error", logData);
  }

  // Send response
  if (!res.headersSent) {
    res.status(statusCode).json({
      error: {
        code: errorCode,
        message: statusCode >= 500 && process.env.NODE_ENV !== "development"
          ? "An internal server error occurred"
          : message,
        details: err.details || {},
        correlationId,
        timestamp: new Date().toISOString(),
        ...(process.env.NODE_ENV === "development" && { stack: err.stack }),
      },
    });
  }
}

// ── Request Size Limits ───────────────────────────────────────────────────────

function requestSizeMiddleware(maxSize = "10mb") {
  const express = require("express");
  return express.json({ limit: maxSize });
}

// ── Graceful Shutdown ───────────────────────────────────────────────────────────

class GracefulShutdown {
  constructor(server, options = {}) {
    this.server = server;
    this.timeout = options.timeout || 30000;
    this.shutdownInProgress = false;
    this.cleanupHandlers = [];
  }

  registerCleanup(handler) {
    this.cleanupHandlers.push(handler);
  }

  async shutdown(signal) {
    if (this.shutdownInProgress) {
      logger.warn("Shutdown already in progress, forcing exit...");
      process.exit(1);
    }

    this.shutdownInProgress = true;
    logger.info(`Graceful shutdown initiated (${signal})`, { timeout: this.timeout });

    const shutdownTimer = setTimeout(() => {
      logger.error("Graceful shutdown timed out, forcing exit");
      process.exit(1);
    }, this.timeout);

    // Stop accepting new connections
    this.server.close(() => {
      logger.info("HTTP server closed, no longer accepting connections");
    });

    // Run cleanup handlers
    for (const handler of this.cleanupHandlers) {
      try {
        await handler();
      } catch (e) {
        logger.error("Cleanup handler failed", { error: e.message });
      }
    }

    clearTimeout(shutdownTimer);
    logger.info("Graceful shutdown completed");
    process.exit(0);
  }

  setup() {
    process.on("SIGTERM", () => this.shutdown("SIGTERM"));
    process.on("SIGINT", () => this.shutdown("SIGINT"));

    // Handle uncaught exceptions
    process.on("uncaughtException", (err) => {
      logger.fatal("Uncaught exception", { error: err.message, stack: err.stack });
      this.shutdown("uncaughtException");
    });

    // Handle unhandled promise rejections
    process.on("unhandledRejection", (reason, promise) => {
      logger.fatal("Unhandled promise rejection", { reason: reason?.message || reason });
      this.shutdown("unhandledRejection");
    });
  }
}

// ── Enhanced Axios Configuration ──────────────────────────────────────────────

function createEnhancedAxios(defaults = {}) {
  const instance = require("axios").create({
    timeout: defaults.timeout || 30000,
    maxRedirects: defaults.maxRedirects || 5,
    maxContentLength: defaults.maxContentLength || 50 * 1024 * 1024, // 50MB
    httpAgent: new (require("http").Agent)({
      keepAlive: true,
      maxSockets: 50,
      maxFreeSockets: 10,
      timeout: 30000,
      freeSocketTimeout: 30000,
    }),
    httpsAgent: new (require("https").Agent)({
      keepAlive: true,
      maxSockets: 50,
      maxFreeSockets: 10,
      timeout: 30000,
      freeSocketTimeout: 30000,
    }),
    ...defaults,
  });

  // Request interceptor for correlation IDs
  instance.interceptors.request.use(
    (config) => {
      // Note: correlation ID should be set per-request if available
      if (!config.headers["X-Correlation-ID"]) {
        config.headers["X-Correlation-ID"] = uuidv4();
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  const isRetryableTransportError = (error) => {
    const msg = `${error?.code || ""} ${error?.message || ""}`.toLowerCase();
    return /socket hang up|econnreset|etimedout|econnaborted|econnrefused|timeout|network/i.test(
      msg
    );
  };

  // Response interceptor: log + retry transient transport failures
  instance.interceptors.response.use(
    (response) => response,
    async (error) => {
      const config = error.config || {};
      config.__retryCount = config.__retryCount || 0;
      const maxRetries = Number.parseInt(process.env.AXIOS_RETRY_MAX || "2", 10);

      if (error.response) {
        logger.warn("HTTP request failed", {
          status: error.response.status,
          url: config.url,
          method: config.method,
          correlationId: config.headers?.["X-Correlation-ID"],
        });
      } else if (error.request) {
        logger.error("HTTP request timeout or no response", {
          url: config.url,
          method: config.method,
          code: error.code,
          retry: config.__retryCount,
        });
      }

      if (
        config.__retryCount < maxRetries &&
        isRetryableTransportError(error) &&
        !config.__noRetry
      ) {
        config.__retryCount += 1;
        const delayMs = Math.min(8000, 1000 * 2 ** config.__retryCount);
        await new Promise((r) => setTimeout(r, delayMs));
        return instance.request(config);
      }

      return Promise.reject(error);
    }
  );

  return instance;
}

// ── Health Check Aggregation ──────────────────────────────────────────────────

async function aggregateHealthChecks(services) {
  const results = {
    overall_status: "healthy",
    timestamp: new Date().toISOString(),
    services: {},
  };

  for (const [name, url] of Object.entries(services)) {
    const start = Date.now();
    try {
      const response = await require("axios").get(`${url}/health`, { timeout: 5000 });
      const duration = Date.now() - start;
      // Accept both "healthy" and "ok" as valid statuses from different services
      const rawStatus = response.data?.status;
      const isHealthy = rawStatus === "healthy" || rawStatus === "ok";
      results.services[name] = {
        status: isHealthy ? rawStatus : (rawStatus || "healthy"),
        response_time_ms: duration,
        details: response.data,
      };
    } catch (error) {
      const duration = Date.now() - start;
      // Defensive: some axios errors have empty or missing messages
      const errMsg = error?.message || error?.toString?.() || "Unknown error";
      logger.warn(`Health check failed for ${name}`, { url, error: errMsg, duration });
      results.services[name] = {
        status: "unhealthy",
        error: errMsg,
        response_time_ms: duration,
      };
      results.overall_status = "degraded";
    }
  }

  // Determine overall status
  const unhealthyCount = Object.values(results.services).filter(s => s.status === "unhealthy").length;
  const totalCount = Object.keys(results.services).length;

  if (unhealthyCount === totalCount && totalCount > 0) {
    results.overall_status = "unhealthy";
  } else if (unhealthyCount > 0) {
    results.overall_status = "degraded";
  }

  return results;
}

// ── Exports ───────────────────────────────────────────────────────────────────

module.exports = {
  // Logger
  logger,
  StructuredLogger,

  // Middleware
  correlationMiddleware,
  requestLoggingMiddleware,
  timeoutMiddleware,
  metricsMiddleware,
  securityHeadersMiddleware,
  requestSizeMiddleware,
  globalErrorHandler,

  // Metrics
  metricsCollector,
  getMetricsEndpoint,

  // Shutdown
  GracefulShutdown,

  // HTTP Client
  createEnhancedAxios,

  // Health
  aggregateHealthChecks,

  // Errors
  AppError,
};
