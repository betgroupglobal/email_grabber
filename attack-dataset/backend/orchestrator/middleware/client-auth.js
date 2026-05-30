"use strict";

/**
 * Optional API-key gate for orchestrator HTTP + WebSocket.
 * When ORCHESTRATOR_API_KEY is unset, all requests pass (dev-friendly).
 */
function createClientAuthMiddleware(apiKey) {
  const PUBLIC_PATHS = new Set(["/health", "/ready", "/live", "/metrics"]);

  function extractKey(req) {
    const auth = req.headers?.authorization;
    if (auth && auth.startsWith("Bearer ")) {
      return auth.slice(7).trim();
    }
    const header = req.headers?.["x-api-key"];
    if (header) return String(header).trim();
    if (req.query?.api_key) return String(req.query.api_key).trim();
    return "";
  }

  function isAuthorized(req) {
    if (!apiKey) return true;
    return extractKey(req) === apiKey;
  }

  const httpMiddleware = (req, res, next) => {
    if (!apiKey) return next();
    if (req.method === "OPTIONS") return next();
    if (PUBLIC_PATHS.has(req.path)) return next();
    if (!isAuthorized(req)) {
      return res.status(401).json({ error: "Unauthorized", code: "ORCHESTRATOR_AUTH_REQUIRED" });
    }
    return next();
  };

  function authorizeWebSocket(req) {
    if (!apiKey) return true;
    return isAuthorized(req);
  }

  return { httpMiddleware, authorizeWebSocket, extractKey };
}

module.exports = { createClientAuthMiddleware };
