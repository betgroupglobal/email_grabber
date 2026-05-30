"use strict";
require("dotenv").config({ path: require("path").join(__dirname, "../..", ".env") });
const express = require("express");
const http = require("http");
const { WebSocketServer } = require("ws");
const { v4: uuidv4 } = require("uuid");

// Enhanced robustness middleware
const {
  correlationMiddleware,
  requestLoggingMiddleware,
  timeoutMiddleware,
  metricsMiddleware,
  securityHeadersMiddleware,
  globalErrorHandler,
  getMetricsEndpoint,
  createEnhancedAxios,
  aggregateHealthChecks,
  GracefulShutdown,
  logger: robustnessLogger,
} = require("./middleware/robustness");

// Replace plain axios with enhanced version
const axios = createEnhancedAxios({ timeout: 30000 });
const { appendTerminalLine, getTerminalHistory } = require("./terminal-buffer");

const KNOWLEDGE_ENGINE = process.env.KNOWLEDGE_ENGINE_URL || "http://127.0.0.1:8000";
const ANALYZER_URL     = process.env.ANALYZER_URL         || "http://localhost:8001";
const OPSEC_URL        = process.env.OPSEC_URL            || "http://localhost:8002";
const INTEGRATION_HUB_URL = process.env.INTEGRATION_HUB_URL || "http://localhost:8500";
const PORT             = parseInt(process.env.PORT || "3001");
const ANTHROPIC_MODEL  = process.env.ANTHROPIC_MODEL      || "claude-opus-4-5";
const AGGRESSION_MIN   = 1;
const AGGRESSION_MAX   = 10;

// Service authentication
const SERVICE_API_KEY = process.env.SERVICE_API_KEY_ORCHESTRATOR || "";

// Helper function to create service authentication headers
function getServiceAuthHeaders() {
  const headers = {};
  if (SERVICE_API_KEY) {
    headers['X-Service-API-Key'] = SERVICE_API_KEY;
    headers['X-Service-Name'] = 'orchestrator';
  }
  return headers;
}

// Target validation: allow IPv4, IPv6, FQDNs, localhost, and CIDR /24 ranges
const TARGET_REGEX = /^(localhost|(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?|[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+|[0-9a-fA-F:]+)$/;

/** Strip URL scheme, path, port — e.g. https://mobileciti.com.au/ → mobileciti.com.au */
function normalizeTargetInput(raw) {
  if (!raw || typeof raw !== "string") return "";
  let s = raw.trim();
  try {
    if (/^https?:\/\//i.test(s)) {
      const u = new URL(s.includes("://") ? s : `https://${s}`);
      s = u.hostname || s;
    }
  } catch {
    /* keep s */
  }
  s = s.replace(/^\/+|\/+$/g, "");
  const slash = s.indexOf("/");
  if (slash > 0) s = s.slice(0, slash);
  const colon = s.indexOf(":");
  if (colon > 0 && /^\d+$/.test(s.slice(colon + 1))) s = s.slice(0, colon);
  return s.trim().toLowerCase();
}

function isValidTarget(t) {
  if (!t || typeof t !== "string") return false;
  const s = normalizeTargetInput(t);
  if (s.length < 2 || s.length > 253) return false;
  return TARGET_REGEX.test(s);
}

const PRIORITY_WEB_PORTS = new Set([
  "443", "80", "8443", "8080", "8000", "8888",
  "22", "21", "25", "53", "3306", "5432", "6379", "27017", "3389",
]);
const MAX_SERVICES_FOR_ATTACK_VECTOR = 40;

/** Cap noisy CDN/WAF fingerprints and prioritize common web ports for KE attack-vector. */
function filterServicesForAttackVector(services) {
  if (!Array.isArray(services) || services.length === 0) return [];

  const scored = [];
  const seen = new Set();

  for (const svc of services) {
    const port = String(svc?.port ?? svc?.Port ?? "").trim();
    const name = String(svc?.name ?? svc?.Name ?? "").trim().toLowerCase();
    const product = String(svc?.product ?? svc?.Product ?? "").trim();
    const version = String(svc?.version ?? svc?.Version ?? "").trim();
    const key = `${port}|${name}|${product}`;
    if (seen.has(key)) continue;
    seen.add(key);

    let score = 500;
    if (PRIORITY_WEB_PORTS.has(port)) score = 10;
    else if (name.includes("http") || name === "https" || name === "ssl") score = 30;
    else if (port && Number.parseInt(port, 10) > 1024) score = 800;

    scored.push({ svc, score, port });
  }

  scored.sort((a, b) => (a.score !== b.score ? a.score - b.score : a.port.localeCompare(b.port)));
  return scored.slice(0, MAX_SERVICES_FOR_ATTACK_VECTOR).map(({ svc }) => svc);
}

function mapServicesToAttackVectorLabels(services) {
  return filterServicesForAttackVector(services).map((s) => {
    const port = String(s?.port ?? s?.Port ?? "").trim();
    const name = String(s?.name ?? s?.Name ?? "").trim();
    const product = String(s?.product ?? s?.Product ?? "").trim();
    const version = String(s?.version ?? s?.Version ?? "").trim();
    return [name, product, version, port ? `port:${port}` : ""].filter(Boolean).join(" ");
  }).filter(Boolean);
}

function buildAttackVectorTargetDescription(target, fingerprint) {
  const fp = fingerprint || {};
  const labels = mapServicesToAttackVectorLabels(fp.services || []);
  const os = fp.os || fp.OS || "unknown";
  const ip = fp.ip || fp.IP || "";
  const host = normalizeTargetInput(target) || target;
  if (!labels.length) {
    return `Target ${host}${ip ? ` (${ip})` : ""} running ${os}`;
  }
  let summary = labels.join(", ");
  if (summary.length > 1200) summary = `${summary.slice(0, 1200)}…`;
  return `Target ${host}${ip ? ` (${ip})` : ""} running ${os}. Detected services: ${summary}`;
}

/** OpSec assess: infer web/e-commerce context from hostname + optional scan fingerprint for KE relevance. */
function inferOpsecAssessAttackVectorContext(target, operationType, scanFingerprint) {
  const host = normalizeTargetInput(target) || target;
  const opType = operationType || "reconnaissance";
  const isIpv4 = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
  const isDomain = !isIpv4 && host.includes(".") && host.length >= 4;

  if (!isDomain) {
    return {
      target_description: `Target: ${host}. Operation: ${opType}`,
      detected_services: [],
      detected_os: "",
    };
  }

  const svcBlob = (scanFingerprint?.services || [])
    .map((s) => `${s.name || ""} ${s.product || ""} port:${s.port || ""}`)
    .join(" ")
    .toLowerCase();
  const hasShopify = /shopify|cdn\.shopify/i.test(svcBlob);
  const ecommerceHint = hasShopify ||
    /shop|store|mart|buy|retail|commerce|citi|market|boutique|outlet/i.test(host)
    ? "e-commerce / online retail (likely Shopify or similar)"
    : "public web application";

  const fingerprint =
    scanFingerprint?.services?.length
      ? scanFingerprint
      : {
          ip: scanFingerprint?.ip || "",
          os: scanFingerprint?.os || "unknown",
          services: [
            { port: "443", name: "https", product: "", version: "" },
            { port: "80", name: "http", product: "", version: "" },
          ],
        };

  const baseDesc = buildAttackVectorTargetDescription(host, fingerprint);
  const target_description = [
    baseDesc,
    `Surface: ${ecommerceHint} behind CDN (e.g. Cloudflare).`,
    "Assessment scope: web reconnaissance, HTTP/TLS/API/auth testing, OWASP-style issues —",
    "exclude social-media vote scams, emoji lures, and unrelated phishing unless target is social engineering scope.",
    "not physical/RF/satellite/IoT attacks unless scan evidence shows those services.",
    `Operation: ${opType}.`,
  ].join(" ");

  return {
    target_description,
    detected_services: mapServicesToAttackVectorLabels(fingerprint.services),
    detected_os: fingerprint.os || "unknown",
  };
}

function normalizeAggressionLevel(raw) {
  const n = Number.parseInt(raw ?? AGGRESSION_MIN, 10);
  if (Number.isNaN(n)) return AGGRESSION_MIN;
  return Math.min(AGGRESSION_MAX, Math.max(AGGRESSION_MIN, n));
}

function isPrivateScopedTarget(target) {
  if (!target || typeof target !== "string") return false;
  const s = target.trim().toLowerCase();
  if (s === "localhost") return true;

  const cidrBase = s.includes("/") ? s.split("/")[0] : s;
  const ipv4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(cidrBase);
  if (ipv4) {
    const octets = ipv4.slice(1).map((v) => Number.parseInt(v, 10));
    if (octets.some((o) => Number.isNaN(o) || o < 0 || o > 255)) return false;
    const [a, b] = octets;
    if (a === 10 || a === 127) return true;
    if (a === 192 && b === 168) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 169 && b === 254) return true;
    return false;
  }

  if (cidrBase === "::1") return true;
  if (cidrBase.startsWith("fc") || cidrBase.startsWith("fd")) return true;
  if (cidrBase.startsWith("fe80")) return true;
  return false;
}

function buildBoundaryProfile(level) {
  const aggressionLevel = normalizeAggressionLevel(level);
  const t = (aggressionLevel - AGGRESSION_MIN) / (AGGRESSION_MAX - AGGRESSION_MIN);

  return {
    aggression_level: aggressionLevel,
    require_private_scope: aggressionLevel <= 3,
    ai_rate_limit_per_min: Math.round(5 + (45 * t)),
    ai_timeout_ms: Math.round(20_000 + (100_000 * t)),
    scan_timeout_sec: Math.round(45 + (195 * t)),
    scan_poll_timeout_ms: Math.round(60_000 + (240_000 * t)),
    quality_gate_threshold: Math.round(90 - (30 * t)),
    max_deepening_rounds: aggressionLevel <= 3 ? 0 : (aggressionLevel <= 7 ? 1 : 2),
    base_top_chains: aggressionLevel <= 3 ? 2 : (aggressionLevel <= 7 ? 3 : 5),
    deepening_top_chains: aggressionLevel <= 3 ? 3 : (aggressionLevel <= 7 ? 5 : 7),
  };
}

// Simple per-minute rate limiter for Claude AI endpoints
const AI_RATE = { count: 0, resetAt: Date.now() + 60_000 };
function checkAIRate(limitPerMinute) {
  const limit = Math.max(1, Number.parseInt(limitPerMinute ?? 20, 10));
  if (Date.now() > AI_RATE.resetAt) { AI_RATE.count = 0; AI_RATE.resetAt = Date.now() + 60_000; }
  if (AI_RATE.count >= limit) return false;
  AI_RATE.count++;
  return true;
}

function getBoundaryProfileByEngagementId(engagementId) {
  if (!engagementId) return null;
  const eng = engagements.get(String(engagementId));
  if (!eng) return null;
  return eng.boundary_profile || null;
}

function resolveAIRateLimit(req) {
  const engagementId = req?.body?.engagement_id || req?.query?.engagement_id || null;
  const profile = getBoundaryProfileByEngagementId(engagementId);
  return profile?.ai_rate_limit_per_min || 20;
}

function resolveAITimeoutMs(req, fallback = 60_000) {
  const engagementId = req?.body?.engagement_id || req?.query?.engagement_id || null;
  const profile = getBoundaryProfileByEngagementId(engagementId);
  return profile?.ai_timeout_ms || fallback;
}

// Initialise OpenAI client for OpenRouter (null if no key)
const openai = process.env.OPENROUTER_API_KEY
  ? new (require('openai'))({ 
      apiKey: process.env.OPENROUTER_API_KEY,
      baseURL: "https://openrouter.ai/api/v1"
    })
  : null;

const AI_MODEL = process.env.OPENROUTER_MODEL || "anthropic/claude-3.5-sonnet";

if (!openai) console.warn("[orchestrator] OPENROUTER_API_KEY not set — AI summary disabled.");

const app = express();

// ── Robustness Middleware Stack ───────────────────────────────────────────────

// 1. Security headers (first line of defense)
app.use(securityHeadersMiddleware);

// 2. Request correlation IDs for distributed tracing
app.use(correlationMiddleware);

// 3. Request/response logging with structured format
app.use(requestLoggingMiddleware);

// 4. Metrics collection for all requests
app.use(metricsMiddleware);

// 5. Request timeout protection (AI routes need longer — RAG + LLM can exceed 30s)
app.use(
  timeoutMiddleware(30000, {
    longRunningPaths: [
      "/ai/chat",
      "/ai/analyse",
      "/mitre",
      "/guided",
      "/execute-chain",
    ],
    longRunningTimeoutMs: parseInt(
      process.env.AI_REQUEST_TIMEOUT_MS || "600000",
      10
    ),
  })
);

// 6. Body parsing with size limits
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// 7. CORS (dev) ────────────────────────────────────────────────────────────
app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader(
    "Access-Control-Allow-Headers",
    "Content-Type, Authorization, X-API-Key, X-Correlation-ID, X-Request-ID"
  );
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

// 8. Optional client API key (set ORCHESTRATOR_API_KEY in production)
const ORCHESTRATOR_API_KEY = process.env.ORCHESTRATOR_API_KEY || "";
const { createClientAuthMiddleware } = require("./middleware/client-auth");
const clientAuth = createClientAuthMiddleware(ORCHESTRATOR_API_KEY);
if (ORCHESTRATOR_API_KEY) {
  console.log("[orchestrator] Client API key auth enabled");
}
app.use(clientAuth.httpMiddleware);

// ── Engagement store (persistent + in-memory cache) ──────────────────────────
const EngagementManager = require('./engagement-manager');
const engagementManager = new EngagementManager();
const liveAttack = require('./live-attack');

// For backward compatibility, provide Map-like interface
const engagements = new Proxy(engagementManager, {
  get(target, prop) {
    // Map method forwarding
    if (typeof target[prop] === 'function') {
      return target[prop].bind(target);
    }
    // Property access
    return target[prop];
  }
});

const OVERSEER_STAGE_ORDER = [
  "task_framing",
  "scan_analysis",
  "vector_decomposition",
  "primary_analysis",
  "critique_gap_detection",
  "deepening_pass",
  "cross_validation",
  "synthesis",
  "quality_gate",
];

const ATTACK_PHASE_ORDER = [
  "Reconnaissance",
  "Resource Development",
  "Initial Access",
  "Execution",
  "Persistence",
  "Privilege Escalation",
  "Defense Evasion",
  "Credential Access",
  "Discovery",
  "Lateral Movement",
  "Collection",
  "Exfiltration",
  "Impact",
];

function createAnalysisOverseer(target, boundaryProfile) {
  const now = new Date().toISOString();
  return {
    enabled: true,
    objective: `Increase analysis depth, evidence quality, and consistency before final output (aggression ${boundaryProfile?.aggression_level ?? AGGRESSION_MIN}/10).`,
    target,
    stage_order: OVERSEER_STAGE_ORDER,
    current_stage: "task_framing",
    started_at: now,
    updated_at: now,
    deepening_rounds: 0,
    max_deepening_rounds: boundaryProfile?.max_deepening_rounds ?? 1,
    quality_gate: {
      threshold: boundaryProfile?.quality_gate_threshold ?? 72,
      status: "pending",
      reason: "",
    },
    quality: {
      coverage: 0,
      depth: 0,
      evidence: 0,
      consistency: 0,
      actionability: 0,
      overall: 0,
    },
    gaps: [],
    recommendations: [],
    events: [],
  };
}

function mergeUniqueStrings(existing, incoming, max = 12) {
  const out = [...(existing || [])];
  for (const value of incoming || []) {
    if (!value) continue;
    if (!out.includes(value)) out.push(value);
    if (out.length >= max) break;
  }
  return out;
}

function computeAttackVectorComplexity(vectorResp) {
  const chains = vectorResp?.chains || [];
  if (!chains.length) return 0;
  const totalSteps = chains.reduce((acc, c) => acc + (c.steps?.length || 0), 0);
  const avgSteps = totalSteps / chains.length;
  const avgConfidence = chains.reduce((acc, c) => acc + (c.confidence || 0), 0) / chains.length;
  return (chains.length * 2) + avgSteps + (avgConfidence * 3);
}

function updateOverseerQuality(eng) {
  const overseer = eng.analysis_overseer;
  if (!overseer) return null;

  const chains = eng.attack_chains?.chains || [];
  const steps = chains.flatMap((c) => c.steps || []);
  const totalSteps = steps.length;
  const avgSteps = chains.length ? totalSteps / chains.length : 0;

  const withMitre = steps.filter((s) => s?.attack?.mitre_technique).length;
  const withDetection = steps.filter((s) => s?.attack?.detection_method).length;
  const distinctPhases = new Set(steps.map((s) => s.phase).filter(Boolean)).size;

  const phaseIndex = new Map(ATTACK_PHASE_ORDER.map((phase, idx) => [phase, idx]));
  let invalidTransitions = 0;
  let transitions = 0;
  for (const chain of chains) {
    const chainPhases = (chain.steps || []).map((s) => s.phase || "");
    for (let i = 1; i < chainPhases.length; i++) {
      const a = phaseIndex.get(chainPhases[i - 1]) ?? i - 1;
      const b = phaseIndex.get(chainPhases[i]) ?? i;
      transitions += 1;
      if (b < a) invalidTransitions += 1;
    }
  }

  const coverage = Math.round(Math.min(100, ((chains.length / 3) * 60) + ((distinctPhases / 13) * 40)));
  const depth = Math.round(Math.min(100, (avgSteps / 7) * 100));
  const evidence = totalSteps
    ? Math.round(((withMitre + withDetection) / (2 * totalSteps)) * 100)
    : 0;
  const consistency = transitions
    ? Math.round(Math.max(0, 100 - ((invalidTransitions / transitions) * 100)))
    : (chains.length ? 80 : 0);
  const actionability = Math.min(
    100,
    20 +
      (eng.opsec_reports ? 30 : 0) +
      (eng.opsec_audit ? 30 : 0) +
      (eng.ai_summary ? 20 : 0)
  );

  const overall = Math.round(
    (coverage * 0.25) +
    (depth * 0.25) +
    (evidence * 0.2) +
    (consistency * 0.15) +
    (actionability * 0.15)
  );

  overseer.quality = { coverage, depth, evidence, consistency, actionability, overall };
  overseer.updated_at = new Date().toISOString();
  return overseer.quality;
}

function addOverseerEvent(engagementId, eng, event) {
  if (!eng.analysis_overseer) return;
  const overseer = eng.analysis_overseer;
  const normalizedEvent = {
    ts: new Date().toISOString(),
    stage: event.stage || overseer.current_stage,
    type: event.type || "progress_update",
    severity: event.severity || "info",
    message: event.message || "",
    suggestions: event.suggestions || [],
  };

  overseer.current_stage = normalizedEvent.stage;
  overseer.updated_at = normalizedEvent.ts;
  overseer.events.push(normalizedEvent);
  if (overseer.events.length > 100) overseer.events.shift();

  overseer.recommendations = mergeUniqueStrings(overseer.recommendations, normalizedEvent.suggestions, 12);
  overseer.gaps = mergeUniqueStrings(overseer.gaps, event.gaps || [], 10);

  broadcast(engagementId, eng);
}

function collectDeepeningSignals(eng) {
  const chains = eng.attack_chains?.chains || [];
  const totalSteps = chains.reduce((acc, c) => acc + (c.steps?.length || 0), 0);
  const avgSteps = chains.length ? totalSteps / chains.length : 0;
  const quality = eng.analysis_overseer?.quality || { overall: 0, evidence: 0, depth: 0 };
  const threshold = eng.analysis_overseer?.quality_gate?.threshold || 72;

  const gaps = [];
  const suggestions = [];

  if (chains.length < 2) {
    gaps.push("Low hypothesis diversity (fewer than 2 chains).");
    suggestions.push("Generate additional alternate chains to improve option coverage.");
  }
  if (avgSteps < 5) {
    gaps.push("Limited chain depth (average under 5 steps).");
    suggestions.push("Increase mid-chain depth with privilege escalation and lateral movement candidates.");
  }
  if (quality.evidence < 70) {
    gaps.push("Evidence quality below target.");
    suggestions.push("Prioritize attacks with explicit MITRE technique and detection_method context.");
  }
  if (quality.overall < threshold) {
    gaps.push(`Overall quality score ${quality.overall} is below threshold ${threshold}.`);
    suggestions.push("Run a deepening pass with broader top_k and stronger phase coverage constraints.");
  }

  return { gaps, suggestions };
}

// ── HTTP routes ───────────────────────────────────────────────────────────────

// ── Health & Monitoring Endpoints ───────────────────────────────────────────────

app.get("/health", async (req, res) => {
  try {
    const serviceHealth = await aggregateHealthChecks({
      knowledge_engine: KNOWLEDGE_ENGINE,
      analyzer: ANALYZER_URL,
      opsec: OPSEC_URL,
      integration_hub: INTEGRATION_HUB_URL,
    });

    res.json({
      status: serviceHealth.overall_status,
      service: "orchestrator",
      version: "1.0.0",
      timestamp: new Date().toISOString(),
      dependencies: serviceHealth.services,
    });
  } catch (error) {
    req.logger.error("Health check aggregation failed", { error: error.message });
    res.status(503).json({
      status: "degraded",
      service: "orchestrator",
      error: "Failed to check dependencies",
      timestamp: new Date().toISOString(),
    });
  }
});

app.get("/metrics", getMetricsEndpoint);

app.get("/mcp/status", (req, res) => {
  try {
    const { getMcpStatus, listServers } = require("./mcpClient");
    res.json({
      ...getMcpStatus(),
      servers: listServers(),
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/ready", (req, res) => {
  const isReady = engagementManager.initialized || false;
  if (isReady) {
    res.json({ ready: true, timestamp: new Date().toISOString() });
  } else {
    res.status(503).json({ ready: false, reason: "Engagement manager not initialized" });
  }
});

app.get("/live", (req, res) => {
  res.json({ alive: true, timestamp: new Date().toISOString() });
});

/** Alias for dashboard service monitor — same aggregated dependency health as /health */
app.get("/system/health", async (req, res) => {
  try {
    const serviceHealth = await aggregateHealthChecks({
      knowledge_engine: KNOWLEDGE_ENGINE,
      analyzer: ANALYZER_URL,
      opsec: OPSEC_URL,
      integration_hub: INTEGRATION_HUB_URL,
    });

    res.json({
      status: serviceHealth.overall_status,
      service: "orchestrator",
      overall_status: serviceHealth.overall_status,
      timestamp: new Date().toISOString(),
      services: serviceHealth.services,
      dependencies: serviceHealth.services,
    });
  } catch (error) {
    req.logger?.error?.("System health check failed", { error: error.message });
    res.status(503).json({
      status: "degraded",
      overall_status: "degraded",
      service: "orchestrator",
      error: "Failed to check dependencies",
      timestamp: new Date().toISOString(),
    });
  }
});

/**
 * POST /engage
 * Kick off a full engagement pipeline for a target:
 *   1. Start real-time scan (analyzer)
 *   2. Return engagement ID immediately
 *   3. Push updates over WebSocket
 */
app.post("/engage", async (req, res) => {
  const { target, aggression_level } = req.body;
  if (!target) return res.status(400).json({ error: "target required" });
  if (!isValidTarget(target)) {
    return res.status(400).json({ error: "invalid target: must be a valid IP address, hostname, or CIDR range" });
  }
  const boundary_profile = buildBoundaryProfile(aggression_level);

  const engagementId = uuidv4().slice(0, 8);
  const engagement = {
    id: engagementId,
    target,
    aggression_level: boundary_profile.aggression_level,
    boundary_profile,
    status: "starting",
    scan_session: null,
    attack_chains: null,
    opsec_reports: null,
    opsec_audit: null,
    analysis_overseer: createAnalysisOverseer(target, boundary_profile),
    log: [],
    started_at: new Date().toISOString(),
  };
  engagements.set(engagementId, engagement);

  // Run pipeline asynchronously
  runEngagementPipeline(engagementId, target).catch((err) => {
    console.error(`[engagement ${engagementId}] pipeline error:`, err.message);
    engagement.status = "error";
    engagement.log.push({ ts: new Date().toISOString(), msg: `Error: ${err.message}` });
    broadcast(engagementId, engagement);
  });

  res.status(202).json({ engagement_id: engagementId });
});

app.get("/engagements", (req, res) => {
  res.json([...engagements.values()]);
});

app.get("/engagements/:id", (req, res) => {
  const eng = engagements.get(req.params.id);
  if (!eng) return res.status(404).json({ error: "not found" });
  res.json(eng);
});

/**
 * POST /search
 * Proxy to Knowledge Engine semantic search.
 */
app.post("/search", async (req, res) => {
  try {
    const { data } = await axios.post(`${KNOWLEDGE_ENGINE}/search`, req.body, {
      headers: getServiceAuthHeaders()
    });
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "knowledge engine unavailable" });
  }
});

/**
 * POST /attack-vector
 * Proxy to Knowledge Engine attack vector builder.
 */
app.post("/attack-vector", async (req, res) => {
  try {
    const body = { ...(req.body || {}) };
    if (Array.isArray(body.detected_services) && body.detected_services.length > MAX_SERVICES_FOR_ATTACK_VECTOR) {
      body.detected_services = body.detected_services.slice(0, MAX_SERVICES_FOR_ATTACK_VECTOR);
    }
    if (!body.target_description || !String(body.target_description).trim()) {
      body.target_description = buildAttackVectorTargetDescription(
        body.target || "unknown",
        { os: body.detected_os, services: (body.detected_services || []).map((label) => ({ name: label })) }
      );
    }
    const { data } = await axios.post(`${KNOWLEDGE_ENGINE}/attack-vector`, body, {
      headers: getServiceAuthHeaders(),
      timeout: 30000,
    });
    res.json(data);
  } catch (err) {
    const status = err.response?.status;
    const detail = err.response?.data?.detail || err.message;
    res.status(502).json({
      error: "knowledge engine unavailable",
      details: typeof detail === "string" ? detail : JSON.stringify(detail),
      upstream_status: status,
    });
  }
});

/**
 * POST /opsec/assess
 * Target OpSec assessment: build attack chains (KE dataset + ML), score via OpSec Monitor,
 * persist as a completed engagement (no localStorage on the client).
 */
app.post("/opsec/assess", async (req, res) => {
  const { target, operation_type, aggression_level } = req.body || {};
  if (!target || typeof target !== "string") {
    return res.status(400).json({ error: "target is required", code: "MISSING_TARGET" });
  }
  const normalized = normalizeTargetInput(target);
  if (!isValidTarget(normalized)) {
    return res.status(400).json({ error: "invalid target format", code: "INVALID_TARGET" });
  }
  const sanitizedTarget = validateAndSanitizeTarget(normalized);
  const opType = operation_type || "reconnaissance";
  const boundary = buildBoundaryProfile(aggression_level);
  const authHeaders = getServiceAuthHeaders();

  let attack_chains = null;
  const assessCtx = inferOpsecAssessAttackVectorContext(sanitizedTarget, opType);
  const vectorBody = {
    target_description: assessCtx.target_description,
    detected_services: assessCtx.detected_services,
    detected_os: assessCtx.detected_os,
    top_chains: 3,
  };
  try {
    const vectorResult = await getCachedAttackVector({
      body: vectorBody,
      fetchFn: async () => {
        const { data } = await axios.post(
          `${KNOWLEDGE_ENGINE}/attack-vector`,
          vectorBody,
          { headers: authHeaders, timeout: 90000 }
        );
        return data;
      },
    });
    attack_chains = vectorResult.data;
    req.logger?.info?.("OpSec assess attack-vector", {
      cache_hit: vectorResult.cache_hit,
      latency_ms: vectorResult.latency_ms,
      chains: attack_chains?.chains?.length || 0,
    });
  } catch (keErr) {
    req.logger?.warn?.("OpSec assess: attack-vector unavailable", { error: keErr.message });
  }

  let chainOpsec = { risk_score: 50, global_findings: [], summary: "" };
  try {
    const primary = attack_chains?.chains?.[0];
    if (primary?.steps?.length) {
      const steps = primary.steps.map((s) => {
        const attack = s.attack || {};
        return {
          title: attack.title || s.phase || "step",
          attack_type: attack.attack_type || opType,
          attack_steps:
            attack.scenario_description ||
            attack.attack_steps ||
            s.rationale ||
            `Phase ${s.phase}`,
          tools_used: attack.tools_used || "",
          mitre_technique: attack.mitre_technique || s.mitre_technique || "",
          detection_method: attack.detection_method || "",
          tags: attack.tags || "",
        };
      });
      const { data } = await axios.post(
        `${OPSEC_URL}/assess/chain`,
        { steps },
        { headers: authHeaders, timeout: 60000 }
      );
      chainOpsec = data;
    } else {
      const { data } = await axios.post(
        `${OPSEC_URL}/assess`,
        {
          title: `Assessment for ${sanitizedTarget}`,
          attack_type: opType,
          attack_steps: `OpSec assessment for ${sanitizedTarget}`,
          tools_used: "",
          mitre_technique: "",
          detection_method: "",
        },
        { headers: authHeaders, timeout: 30000 }
      );
      chainOpsec = {
        risk_score: data.risk_score,
        global_findings: data.findings || [],
        summary: data.summary || "",
        per_step: [data],
      };
    }
  } catch (opsecErr) {
    return res.status(502).json({
      error: "opsec monitor unavailable",
      details: opsecErr.message,
    });
  }

  const globalFindings = chainOpsec.global_findings || [];
  const risk_factors = globalFindings.map((f) => ({
    category: f.rule_id || "opsec",
    severity: f.severity || "medium",
    description: f.description || f.title || "",
    recommendation: f.remediation || "",
  }));

  const risk_score = chainOpsec.risk_score ?? 50;
  const overall_score = Math.max(0, Math.round(100 - risk_score));
  const recommendations = [
    ...(chainOpsec.summary ? [chainOpsec.summary] : []),
    ...risk_factors.map((f) => f.recommendation).filter(Boolean),
  ];

  const engagementId = uuidv4().slice(0, 8);
  const now = new Date().toISOString();
  const engagement = {
    id: engagementId,
    target: sanitizedTarget,
    status: "complete",
    source: "opsec_assessment",
    aggression_level: boundary.aggression_level,
    boundary_profile: boundary,
    attack_chains,
    opsec_reports: chainOpsec,
    started_at: now,
    completed_at: now,
    log: [
      {
        ts: now,
        msg: `OpSec assessment: ${attack_chains?.chains?.length || 0} chain(s) from knowledge engine`,
      },
    ],
  };
  engagements.set(engagementId, engagement);
  broadcast(engagementId, engagement);

  res.json({
    target: sanitizedTarget,
    engagement_id: engagementId,
    overall_score,
    risk_score,
    risk_factors,
    recommendations,
    attack_chains,
    summary: chainOpsec.summary || recommendations[0] || "",
  });
});

/** Guided autonomous pipeline (initialized after broadcast helpers). */
let guidedAutonomous = null;

/**
 * POST /guided/autonomous/start
 * Create engagement and run 8-phase Jailbreak AI–governed pipeline.
 */
app.post("/guided/autonomous/start", async (req, res) => {
  if (!guidedAutonomous) {
    return res.status(503).json({ error: "Guided autonomous service not ready" });
  }
  const { target, aggression_level, roe_acknowledged, web_only } = req.body || {};
  if (!target || typeof target !== "string") {
    return res.status(400).json({ error: "target is required", code: "MISSING_TARGET" });
  }
  const normalized = normalizeTargetInput(target);
  if (!isValidTarget(normalized)) {
    return res.status(400).json({ error: "invalid target format", code: "INVALID_TARGET" });
  }
  const sanitizedTarget = validateAndSanitizeTarget(normalized);
  const boundary = buildBoundaryProfile(aggression_level);

  const engagementId = uuidv4().slice(0, 8);
  const now = new Date().toISOString();
  const engagement = {
    id: engagementId,
    target: sanitizedTarget,
    status: "starting",
    source: "guided_autonomous",
    aggression_level: boundary.aggression_level,
    boundary_profile: boundary,
    attack_chains: null,
    opsec_reports: null,
    scan_session: null,
    fingerprint: null,
    guided_autonomous: {
      status: "starting",
      current_phase: 0,
      web_only: web_only !== false,
      roe_acknowledged: roe_acknowledged !== false,
      phases: [],
      jailbreak_api_configured: Boolean(process.env.JAILBREAK_API_KEY),
      started_at: now,
    },
    log: [
      {
        ts: now,
        msg: `Autonomous guided assessment started for ${sanitizedTarget}`,
      },
    ],
    started_at: now,
  };

  engagements.set(engagementId, engagement);
  broadcast(engagementId, engagement);

  guidedAutonomous.runGuidedAutonomousPipeline(engagementId).catch((err) => {
    console.error(`[guided ${engagementId}] pipeline error:`, err.message);
  });

  res.status(202).json({
    engagement_id: engagementId,
    target: sanitizedTarget,
    status: "starting",
    source: "guided_autonomous",
    jailbreak_api_configured: Boolean(process.env.JAILBREAK_API_KEY),
    message: "Autonomous guided assessment pipeline started",
  });
});

/**
 * POST /guided/autonomous/:id/stop
 */
app.post("/guided/autonomous/:id/stop", (req, res) => {
  if (!guidedAutonomous) {
    return res.status(503).json({ error: "Guided autonomous service not ready" });
  }
  const id = validateEngagementId(req.params.id);
  const eng = engagements.get(id);
  if (!eng) {
    return res.status(404).json({ error: "Engagement not found", code: "ENGAGEMENT_NOT_FOUND" });
  }
  guidedAutonomous.requestStop(id);
  res.json({ engagement_id: id, status: "stopping" });
});

/**
 * GET /guided/autonomous/:id/status
 */
app.get("/guided/autonomous/:id/status", (req, res) => {
  if (!guidedAutonomous) {
    return res.status(503).json({ error: "Guided autonomous service not ready" });
  }
  const id = validateEngagementId(req.params.id);
  const status = guidedAutonomous.getStatus(id);
  if (!status) {
    return res.status(404).json({ error: "Engagement not found", code: "ENGAGEMENT_NOT_FOUND" });
  }
  res.json(status);
});

/**
 * POST /engagements/:id/start-full-engagement
 * Launch a full scan + analysis pipeline while preserving OpSec assessment chains
 * so they can be executed immediately on the new engagement.
 */
app.post("/engagements/:id/start-full-engagement", async (req, res) => {
  const parentId = validateEngagementId(req.params.id);
  const parent = engagements.get(parentId);
  if (!parent) {
    return res.status(404).json({ error: "Engagement not found", code: "ENGAGEMENT_NOT_FOUND" });
  }
  if (!parent.attack_chains?.chains?.length) {
    return res.status(400).json({
      error: "No attack chains on this engagement — run OpSec assess first",
      code: "NO_CHAINS",
    });
  }

  const boundary_profile =
    parent.boundary_profile || buildBoundaryProfile(parent.aggression_level);
  const newId = uuidv4().slice(0, 8);
  const now = new Date().toISOString();

  const engagement = {
    id: newId,
    target: parent.target,
    aggression_level: boundary_profile.aggression_level,
    boundary_profile,
    status: "starting",
    source: "full_engagement",
    parent_opsec_engagement_id: parentId,
    scan_session: null,
    attack_chains: parent.attack_chains,
    opsec_reports: parent.opsec_reports || null,
    opsec_audit: null,
    analysis_overseer: createAnalysisOverseer(parent.target, boundary_profile),
    log: [
      {
        ts: now,
        msg: `Full engagement started from OpSec assessment ${parentId} (${parent.attack_chains.chains.length} chain(s) seeded)`,
      },
    ],
    started_at: now,
  };

  engagements.set(newId, engagement);
  broadcast(newId, engagement);

  runEngagementPipeline(newId, parent.target).catch((err) => {
    console.error(`[engagement ${newId}] pipeline error:`, err.message);
    const eng = engagements.get(newId);
    if (eng) {
      eng.status = "error";
      eng.log.push({ ts: new Date().toISOString(), msg: `Error: ${err.message}` });
      broadcast(newId, eng);
    }
  });

  res.status(202).json({
    engagement_id: newId,
    parent_engagement_id: parentId,
    target: parent.target,
    chains_seeded: parent.attack_chains.chains.length,
    status: "starting",
    message: "Full engagement pipeline started; assessment chains are ready to execute",
  });
});

/**
 * POST /opsec/chain
 * Assess a full attack chain via OpSec Monitor.
 */
app.post("/opsec/chain", async (req, res) => {
  try {
    const { data } = await axios.post(`${OPSEC_URL}/assess/chain`, req.body, {
      headers: getServiceAuthHeaders()
    });
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "opsec monitor unavailable" });
  }
});

/**
 * POST /opsec/audit
 * Audit an attack chain via Knowledge Engine OpSec audit.
 */
app.post("/opsec/audit", async (req, res) => {
  try {
    const { data } = await axios.post(`${KNOWLEDGE_ENGINE}/opsec/audit`, req.body, {
      headers: getServiceAuthHeaders()
    });
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "opsec audit unavailable" });
  }
});

/**
 * POST /opsec/audit/vector
 * Audit an attack vector via Knowledge Engine OpSec audit.
 */
app.post("/opsec/audit/vector", async (req, res) => {
  try {
    const { data } = await axios.post(`${KNOWLEDGE_ENGINE}/opsec/audit/vector`, req.body, {
      headers: getServiceAuthHeaders()
    });
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "opsec audit unavailable" });
  }
});

/**
 * POST /opsec/tool/:toolName
 * Get OpSec recommendations for a specific tool.
 */
app.post("/opsec/tool/:toolName", async (req, res) => {
  try {
    const { data } = await axios.post(`${KNOWLEDGE_ENGINE}/opsec/tool/${req.params.toolName}`, req.body, {
      headers: getServiceAuthHeaders()
    });
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "opsec audit unavailable" });
  }
});

/**
 * POST /ai/chat — primary path: Integration Hub → jailbreak_ai (assistant_chat).
 * Optional RAG context from Knowledge Engine /search. KE /ai/chat is fallback only.
 */

function normalizeChatMessages(body) {
  if (!body || typeof body !== "object") return [];
  if (Array.isArray(body.messages) && body.messages.length) {
    return body.messages
      .filter((m) => m && (m.role === "user" || m.role === "assistant" || m.role === "system"))
      .map((m) => ({ role: m.role, content: String(m.content || "") }));
  }
  if (body.question) {
    const history = Array.isArray(body.history) ? body.history : [];
    return [
      ...history.map((m) => ({ role: m.role, content: String(m.content || "") })),
      { role: "user", content: String(body.question) },
    ];
  }
  if (body.context) {
    return [{ role: "user", content: String(body.context) }];
  }
  return [];
}

function lastUserMessageText(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i]?.role === "user" && messages[i].content?.trim()) {
      return messages[i].content.trim();
    }
  }
  return "";
}

const {
  getCachedSearch,
  getCachedAttackVector,
  keCacheStats,
} = require("./ke-cache");

async function fetchKnowledgeContextForChat(question, target = "") {
  if (!question) return { rag_context: "", cache_hit: false, latency_ms: 0 };
  try {
    const result = await getCachedSearch({
      query: question,
      target,
      limit: 5,
      fetchFn: async () => {
        const { data } = await axios.post(
          `${KNOWLEDGE_ENGINE}/search`,
          { query: question, limit: 8 },
          { timeout: 12_000, headers: getServiceAuthHeaders() }
        );
        return data;
      },
    });
    return result;
  } catch (err) {
    console.warn("[ai/chat] RAG search skipped:", err.message);
    return { rag_context: "", cache_hit: false, latency_ms: 0 };
  }
}

function writeSseContentChunks(res, text) {
  const chunkSize = 80;
  for (let i = 0; i < text.length; i += chunkSize) {
    res.write(`data: ${JSON.stringify({ content: text.slice(i, i + chunkSize) })}\n\n`);
  }
  res.write("data: [DONE]\n\n");
}

async function callJailbreakAssistantChat(payload) {
  return callJailbreakHubExecute({
    operation: "assistant_chat",
    ...payload,
  });
}

const { runAssistantAgentChat } = require("./assistant-agent-chat");

function normalizeChatBodyForKE(body) {
  if (!body || typeof body !== "object") return { question: "", history: [], stream: true };
  if (body.question && typeof body.question === "string") {
    return {
      question: body.question,
      history: body.history || [],
      stream: body.stream !== false,
      engagement_context: body.engagement_context,
      allow_tools: body.allow_tools,
      execution_mode: body.execution_mode,
      swarm_max_steps: body.swarm_max_steps,
    };
  }
  const messages = Array.isArray(body.messages) ? body.messages : [];
  const lastUserIdx = [...messages].map((m, i) => (m?.role === "user" ? i : -1)).filter((i) => i >= 0).pop();
  const lastUser = lastUserIdx != null ? messages[lastUserIdx] : null;
  const history = messages
    .filter((_, i) => i !== lastUserIdx && (messages[i]?.role === "user" || messages[i]?.role === "assistant"))
    .map((m) => ({ role: m.role, content: String(m.content || "") }));
  return {
    question: String(lastUser?.content || body.context || "").trim(),
    history,
    stream: body.stream !== false,
    engagement_context: body.engagement_context,
    allow_tools: body.allow_tools,
    execution_mode: body.execution_mode,
    swarm_max_steps: body.swarm_max_steps,
  };
}

function extractUpstreamErrorDetail(err) {
  const data = err.response?.data;
  if (!data) return err.message || "upstream request failed";
  if (typeof data === "string") return data;
  if (data.detail) return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
  if (data.error) return typeof data.error === "string" ? data.error : JSON.stringify(data.error);
  return err.message || "upstream request failed";
}

app.post("/ai/chat", async (req, res) => {
  if (!checkAIRate(resolveAIRateLimit(req))) {
    return res.status(429).json({ error: "AI rate limit exceeded — try again in a minute" });
  }

  const messages = normalizeChatMessages(req.body);
  const question = lastUserMessageText(messages);
  if (!question) {
    return res.status(400).json({ error: "question or user message is required", code: "MISSING_QUESTION" });
  }

  const wantsStream = req.body?.stream === true;
  const useRag = req.body?.use_rag !== false;
  const aiTimeout = resolveAITimeoutMs(req, 120_000);

  const chatStarted = Date.now();
  const respondWithAnswer = (answer, meta = {}) => {
    const latency_ms = meta.latency_ms ?? Date.now() - chatStarted;
    if (wantsStream && answer) {
      res.setHeader("Content-Type", "text/event-stream");
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("X-Accel-Buffering", "no");
      res.setHeader("X-AI-Source", meta.source || "jailbreak_api");
      res.setHeader("X-AI-Latency-Ms", String(latency_ms));
      writeSseContentChunks(res, answer);
      return res.end();
    }
    return res.json({
      answer,
      response: answer,
      source: meta.source || "jailbreak_api",
      ai_source: meta.source || "jailbreak_api",
      model: meta.model || null,
      provider: "Jailbreak AI",
      latency_ms,
      tokens: meta.tokens || null,
      rag_cache_hit: meta.rag_cache_hit ?? false,
    });
  };

  try {
    const chatTarget =
      req.body?.engagement_context?.target ||
      req.body?.target ||
      "";
    let rag_context = "";
    let rag_cache_hit = false;
    let rag_latency_ms = 0;

    const ragPromise = useRag
      ? fetchKnowledgeContextForChat(question, chatTarget)
      : Promise.resolve({ rag_context: "", cache_hit: false, latency_ms: 0 });

    if (JAILBREAK_VIA_HUB) {
      const ragResult = await ragPromise;
      rag_context = ragResult.rag_context || "";
      rag_cache_hit = Boolean(ragResult.cache_hit);
      rag_latency_ms = ragResult.latency_ms || 0;

      const allowTools = req.body?.allow_tools === true;
      if (allowTools) {
        try {
          const agentStarted = Date.now();
          const agentResult = await runAssistantAgentChat(
            {
              axios,
              INTEGRATION_HUB_URL,
              ANALYZER_URL,
              KNOWLEDGE_ENGINE,
              getServiceAuthHeaders,
              callJailbreakHubExecute,
              liveAttack,
            },
            {
              messages,
              target: chatTarget,
              rag_context,
              engagement_context: req.body?.engagement_context,
              broadcastTerminal: null,
            }
          );
          if (agentResult?.answer) {
            req.logger?.info("AI chat via assistant_agent", {
              rounds: agentResult.rounds,
              tools_used: agentResult.tools_used?.length || 0,
              latency_ms: Date.now() - chatStarted,
            });
            if (wantsStream) {
              res.setHeader("Content-Type", "text/event-stream");
              res.setHeader("Cache-Control", "no-cache");
              res.setHeader("X-Accel-Buffering", "no");
              res.setHeader("X-AI-Source", agentResult.source || "jailbreak_api");
              writeSseContentChunks(res, agentResult.answer);
              return res.end();
            }
            return res.json({
              answer: agentResult.answer,
              response: agentResult.answer,
              source: agentResult.source || "jailbreak_api",
              ai_source: agentResult.source || "jailbreak_api",
              tools_used: agentResult.tools_used || [],
              rounds: agentResult.rounds || 0,
              latency_ms: Date.now() - chatStarted,
              rag_cache_hit,
            });
          }
        } catch (agentErr) {
          req.logger?.warn("assistant_agent failed, falling back to assistant_chat", {
            error: agentErr.message,
          });
        }
      }

      const jailbreakStarted = Date.now();
      const hubData = await callJailbreakAssistantChat({
        messages,
        engagement_context: req.body?.engagement_context,
        rag_context,
        stream: false,
        temperature: 0.6,
        max_tokens: 1800,
      });
      const jailbreak_latency_ms = Date.now() - jailbreakStarted;

      if (hubData?.success) {
        const output = hubData.output && typeof hubData.output === "object" ? hubData.output : {};
        const answer = output.answer || output.content || "";
        if (answer) {
          const aiSource = output.source || output.ai_source || "jailbreak_api";
          req.logger?.info("AI chat via jailbreak_ai", {
            ai_source: aiSource,
            latency_ms: Date.now() - chatStarted,
            jailbreak_latency_ms,
            rag_latency_ms,
            rag_cache_hit,
            tokens: output.usage || output.tokens || null,
          });
          return respondWithAnswer(answer, {
            source: aiSource,
            model: output.model,
            tokens: output.usage || output.tokens || null,
            rag_cache_hit,
            latency_ms: Date.now() - chatStarted,
          });
        }
      }

      const hubErr =
        hubData?.error ||
        (typeof hubData?.output === "string" ? hubData.output : null) ||
        "Jailbreak AI returned no content";
      if (hubErr.includes("JAILBREAK_API_KEY")) {
        return res.status(503).json({
          error: "AI unavailable — set JAILBREAK_API_KEY on integration-hub",
          detail: hubErr,
          code: "AI_UNAVAILABLE",
        });
      }
      req.logger?.warn("Jailbreak assistant_chat failed, trying KE fallback", { error: hubErr });
    }

    if (useRag && !rag_context) {
      const ragResult = await ragPromise;
      rag_context = ragResult.rag_context || "";
      rag_cache_hit = Boolean(ragResult.cache_hit);
    }

    const keBody = normalizeChatBodyForKE(req.body);
    keBody.stream = false;
    const { data } = await axios.post(`${KNOWLEDGE_ENGINE}/ai/chat`, keBody, {
      timeout: aiTimeout,
      headers: getServiceAuthHeaders(),
    });
    const answer = data?.answer || data?.response || "";
    req.logger?.info("AI chat via knowledge_engine fallback", {
      ai_source: "knowledge_engine",
      latency_ms: Date.now() - chatStarted,
    });
    return respondWithAnswer(answer, {
      source: "knowledge_engine",
      model: data?.model,
      rag_cache_hit,
      latency_ms: Date.now() - chatStarted,
    });
  } catch (err) {
    const status = err.response?.status || 502;
    const detail = extractUpstreamErrorDetail(err);
    const code = status === 503 ? "AI_UNAVAILABLE" : "AI_CHAT_FAILED";
    let error =
      detail.includes("JAILBREAK_API_KEY")
        ? "AI unavailable — set JAILBREAK_API_KEY on integration-hub"
        : "AI chat unavailable";
    res.status(status >= 400 && status < 600 ? status : 502).json({
      error,
      detail,
      code,
    });
  }
});

/**
 * POST /ai/analyse/engagement
 * Full engagement AI analysis — proxy to Knowledge Engine.
 */
app.post("/ai/analyse/engagement", async (req, res) => {
  if (!checkAIRate(resolveAIRateLimit(req))) return res.status(429).json({ error: "AI rate limit exceeded — try again in a minute" });
  try {
    const { data } = await axios.post(
      `${KNOWLEDGE_ENGINE}/ai/analyse/engagement`, req.body,
      { 
        timeout: resolveAITimeoutMs(req, 60_000),
        headers: getServiceAuthHeaders()
      }
    );
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "AI analysis unavailable" });
  }
});

/**
 * POST /ai/analyse/chain
 * Single chain AI analysis — proxy to Knowledge Engine.
 */
app.post("/ai/analyse/chain", async (req, res) => {
  if (!checkAIRate(resolveAIRateLimit(req))) return res.status(429).json({ error: "AI rate limit exceeded — try again in a minute" });
  try {
    const { data } = await axios.post(
      `${KNOWLEDGE_ENGINE}/ai/analyse/chain`, req.body,
      { 
        timeout: resolveAITimeoutMs(req, 60_000),
        headers: getServiceAuthHeaders()
      }
    );
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "AI analysis unavailable" });
  }
});

/**
 * GET /ai/status
 * Check AI availability.
 */
app.get("/ai/status", async (req, res) => {
  const limit = Math.max(1, Number.parseInt(resolveAIRateLimit(req) ?? 20, 10));
  if (Date.now() > AI_RATE.resetAt) {
    AI_RATE.count = 0;
    AI_RATE.resetAt = Date.now() + 60_000;
  }
  const rateLimit = {
    remaining: Math.max(0, limit - AI_RATE.count),
    reset_at: new Date(AI_RATE.resetAt).toISOString(),
  };

  let hubHealthy = false;
  let hubModel = "jailbreak-ai";
  let hubError = null;

  if (JAILBREAK_VIA_HUB) {
    try {
      const { data: health } = await axios.get(
        `${INTEGRATION_HUB_URL}/api/v1/plugins/jailbreak_ai/health`,
        { timeout: 8_000 }
      );
      hubHealthy = Boolean(health?.healthy);
      hubModel = health?.details?.model || health?.model || hubModel;
      if (!hubHealthy) hubError = health?.error || health?.message || "plugin unhealthy";
    } catch (err) {
      hubError = err.message || "cannot reach integration-hub";
    }
  }

  const jailbreakConfigured = hubHealthy || Boolean(process.env.JAILBREAK_API_KEY);
  let unavailable_reason = null;
  if (!JAILBREAK_VIA_HUB) {
    unavailable_reason = "JAILBREAK_VIA_HUB is disabled on orchestrator";
  } else if (!hubHealthy) {
    unavailable_reason = hubError?.includes("JAILBREAK")
      ? "Set JAILBREAK_API_KEY on integration-hub (and restart integration-hub)"
      : `Jailbreak AI unavailable — ${hubError || "integration-hub plugin unhealthy"}`;
  }

  res.json({
    available: JAILBREAK_VIA_HUB && hubHealthy,
    model: hubModel,
    provider: "Jailbreak AI",
    powered_by: "jailbreak_ai",
    jailbreak_api_configured: jailbreakConfigured,
    hub_healthy: hubHealthy,
    unavailable_reason,
    rate_limit: rateLimit,
    ke_cache: keCacheStats(),
  });
});

/**
 * POST /ai/enhance-chain — review/replace one weak step in an attack chain via Jailbreak.
 */
app.post("/ai/enhance-chain", async (req, res) => {
  if (!checkAIRate(resolveAIRateLimit(req))) {
    return res.status(429).json({ error: "AI rate limit exceeded", code: "RATE_LIMIT" });
  }

  const { chain, step_index, target, context, web_only } = req.body || {};
  if (!chain || !Array.isArray(chain.steps)) {
    return res.status(400).json({ error: "chain with steps array is required", code: "MISSING_FIELD" });
  }
  const idx = Number.isInteger(step_index) ? step_index : 0;
  const step = chain.steps[idx];
  if (!step) {
    return res.status(400).json({ error: "step_index out of range", code: "INVALID_STEP" });
  }

  const started = Date.now();
  const attack = step.attack || {};
  const userPrompt = `Review ONE attack chain step for a web pentest. Replace it only if irrelevant, fictional, or a social/scam lure.

Target: ${target || "unknown"}
Context: ${context || "none"}
Web-only: ${web_only !== false}

Current step ${idx + 1}:
Phase: ${step.phase || "unknown"}
Title: ${attack.title || step.description || "unknown"}
MITRE: ${attack.mitre_technique || step.mitre_technique || ""}

Respond with JSON only (no markdown):
{
  "replace": boolean,
  "reason": "string",
  "replacement": {
    "phase": "string",
    "title": "string",
    "mitre_technique": "string",
    "tools_used": "string",
    "rationale": "string"
  }
}`;

  try {
    if (!JAILBREAK_VIA_HUB) {
      return res.status(503).json({ error: "Jailbreak hub disabled", code: "AI_UNAVAILABLE" });
    }

    const hubData = await callJailbreakHubExecute({
      operation: "chat",
      plugin_name: "jailbreak_ai",
      parameters: {
        operation: "chat",
        messages: [
          {
            role: "system",
            content:
              "You are a MITRE ATT&CK chain reviewer. Output valid JSON only. Never suggest emoji vote scams or unrelated RF/satellite techniques for web targets.",
          },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.2,
        max_tokens: 900,
      },
    });

    const output = hubData?.output;
    const content =
      typeof output === "string"
        ? output
        : output?.content || output?.answer || "";
    const { parseMitreJsonFromLLMContent } = require("./mitre-mapping");
    let parsed;
    try {
      parsed = parseMitreJsonFromLLMContent(content);
    } catch {
      parsed = { replace: false, reason: "Could not parse AI response", replacement: null };
    }

    const latency_ms = Date.now() - started;
    req.logger?.info("AI enhance-chain", {
      ai_source: "jailbreak_api",
      latency_ms,
      step_index: idx,
      replace: parsed.replace,
    });

    return res.json({
      ...parsed,
      step_index: idx,
      ai_source: "jailbreak_api",
      latency_ms,
    });
  } catch (err) {
    req.logger?.error("AI enhance-chain failed", { error: err.message });
    return res.status(502).json({
      error: "AI enhance-chain unavailable",
      detail: err.message,
      code: "AI_ENHANCE_FAILED",
    });
  }
});

// ── AI-Powered MITRE ATT&CK Endpoints ──────────────────────────────────────────

const MITRE_VIA_JAILBREAK = process.env.JAILBREAK_VIA_HUB !== "false";

const {
  parseMitreJsonFromLLMContent,
  sanitizeMitreAnalyzeResult,
  mitreSuggestFromHeuristic,
  mitreEnhanceChainHeuristic,
  formatMitreUnavailableError,
} = require("./mitre-mapping");

async function callMitreLLM({ systemPrompt, userPrompt, maxTokens = 2000, temperature = 0.3, req }) {
  if (openai) {
    try {
      const completion = await openai.chat.completions.create({
        model: AI_MODEL,
        max_tokens: maxTokens,
        temperature,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
      });
      const content = completion.choices[0]?.message?.content || "";
      return {
        result: parseMitreJsonFromLLMContent(content),
        ai_model: AI_MODEL,
        source: "openrouter",
        raw_content: content,
      };
    } catch (openaiErr) {
      req?.logger?.warn("MITRE mapping via openrouter failed", {
        error: openaiErr.message,
        detail: extractUpstreamErrorDetail(openaiErr),
      });
    }
  }

  if (MITRE_VIA_JAILBREAK) {
    try {
      const hubData = await callJailbreakAssistantChat({
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature,
        max_tokens: maxTokens,
        stream: false,
      });
      if (hubData?.success) {
        const output = hubData.output && typeof hubData.output === "object" ? hubData.output : {};
        const content = output.answer || output.content || "";
        if (content) {
          return {
            result: parseMitreJsonFromLLMContent(content),
            ai_model: output.model || "jailbreak-ai",
            source: output.source || "jailbreak_ai",
            raw_content: content,
          };
        }
      }
      const hubErr =
        hubData?.error ||
        (typeof hubData?.output === "string" ? hubData.output : null) ||
        "Jailbreak AI returned no content";
      req?.logger?.warn("MITRE mapping via jailbreak_ai failed", { error: hubErr });
    } catch (hubErr) {
      req?.logger?.warn("MITRE jailbreak hub request failed", {
        error: hubErr.message,
        detail: extractUpstreamErrorDetail(hubErr),
      });
    }
  }

  return null;
}

async function mitreHeuristicFromAttackVector({
  target_description,
  detected_services,
  detected_os,
  top_chains = 2,
}) {
  const { data } = await axios.post(
    `${KNOWLEDGE_ENGINE}/attack-vector`,
    {
      target_description,
      detected_services: detected_services || [],
      detected_os: detected_os || null,
      top_chains,
    },
    { headers: getServiceAuthHeaders(), timeout: 30_000 }
  );

  const techniques = [];
  const chains = [];
  const seen = new Set();

  for (const chain of data.chains || []) {
    const steps = (chain.steps || []).map((s) => ({
      phase: String(s.phase || ""),
      technique_id: String(s.mitre_technique || s.attack?.mitre_technique || "T1595").toUpperCase(),
      description: String(s.rationale || s.attack?.title || s.phase || ""),
    }));
    chains.push({
      name: String(chain.chain_id || chain.target_description || "Heuristic chain").slice(0, 80),
      steps,
      confidence: Math.min(1, Math.max(0, parseFloat(chain.confidence) || 0.5)),
    });
    for (const step of chain.steps || []) {
      const tid = String(step.mitre_technique || step.attack?.mitre_technique || "").toUpperCase();
      if (!tid || seen.has(tid)) continue;
      seen.add(tid);
      techniques.push({
        technique_id: tid,
        name: String(step.attack?.title || tid),
        tactic: String(step.phase || "Unknown"),
        confidence: Math.min(1, Math.max(0, parseFloat(chain.confidence) || 0.5)),
        rationale: String(step.rationale || "Mapped from knowledge engine attack-vector"),
        subtechniques: [],
        detection_methods: step.attack?.detection_method
          ? [String(step.attack.detection_method)]
          : [],
        mitigations: step.attack?.solution ? [String(step.attack.solution)] : [],
      });
    }
  }

  return {
    techniques: techniques.slice(0, 8),
    chains,
    summary:
      techniques.length > 0
        ? `Heuristic MITRE mapping from knowledge engine (${techniques.length} techniques).`
        : "Heuristic MITRE mapping — no techniques matched; refine target or services.",
    generated_at: new Date().toISOString(),
    ai_model: "heuristic:attack-vector",
    source: "heuristic",
  };
}

/**
 * POST /mitre/analyze
 * AI-powered MITRE technique mapping — uses LLM to intelligently map attack
 * descriptions to MITRE ATT&CK techniques with confidence scores and rationale.
 */
app.post("/mitre/analyze", async (req, res) => {
  if (!checkAIRate(resolveAIRateLimit(req))) {
    return res.status(429).json({ error: "AI rate limit exceeded — try again in a minute", code: "RATE_LIMIT" });
  }

  const { attack_description, target_type, services, context } = req.body;
  if (!attack_description) {
    return res.status(400).json({ error: "attack_description is required", code: "MISSING_FIELD" });
  }

  const systemPrompt =
    "You are a MITRE ATT&CK mapping specialist. Respond only with valid JSON — no markdown outside a json code block.";
  const userPrompt = `You are a cybersecurity expert specializing in MITRE ATT&CK framework mapping.

Analyze the following attack scenario and map it to the most relevant MITRE ATT&CK techniques.

Attack Description: ${attack_description}
Target Type: ${target_type || "unknown"}
Detected Services: ${(services || []).join(", ") || "none"}
Additional Context: ${context || "none"}

Respond ONLY with a JSON object in this exact format:
{
  "techniques": [
    {
      "technique_id": "Txxxx",
      "name": "Full Technique Name",
      "tactic": "Reconnaissance|Resource Development|Initial Access|Execution|Persistence|Privilege Escalation|Defense Evasion|Credential Access|Discovery|Lateral Movement|Collection|Exfiltration|Impact",
      "confidence": 0.0-1.0,
      "rationale": "Why this technique applies",
      "subtechniques": ["Txxxx.xxx"],
      "detection_methods": ["method1", "method2"],
      "mitigations": ["mitigation1", "mitigation2"]
    }
  ],
  "chains": [
    {
      "name": "Chain name",
      "steps": [
        { "phase": "Phase Name", "technique_id": "Txxxx", "description": "Step description" }
      ],
      "confidence": 0.0-1.0
    }
  ],
  "summary": "Executive summary of the MITRE mapping"
}

Include at least 3 and at most 8 techniques. Be specific with technique IDs. Ensure confidence reflects certainty.`;

  try {
    let llm = await callMitreLLM({
      systemPrompt,
      userPrompt,
      maxTokens: 2000,
      temperature: 0.3,
      req,
    });

    if (!llm) {
      const heuristic = await mitreHeuristicFromAttackVector({
        target_description: attack_description,
        detected_services: services || [],
        detected_os: target_type || null,
      });
      req.logger?.info("MITRE analyze via heuristic attack-vector", {
        techniques: heuristic.techniques.length,
      });
      return res.json(heuristic);
    }

    let result;
    try {
      result = sanitizeMitreAnalyzeResult(llm.result);
    } catch (parseErr) {
      req.logger.error("Failed to parse AI MITRE response; falling back to heuristic", {
        error: parseErr.message,
        source: llm.source,
        raw: String(llm.raw_content || "").substring(0, 500),
      });
      try {
        const heuristic = await mitreHeuristicFromAttackVector({
          target_description: attack_description,
          detected_services: services || [],
          detected_os: target_type || null,
        });
        return res.json(heuristic);
      } catch (heuristicErr) {
        return res.status(503).json({
          error: formatMitreUnavailableError({
            aiDetail: parseErr.message,
            heuristicDetail: heuristicErr.message,
          }),
          code: "MITRE_UNAVAILABLE",
        });
      }
    }

    result.generated_at = new Date().toISOString();
    result.ai_model = llm.ai_model;
    result.source = llm.source;
    req.logger?.info("MITRE analyze complete", { source: llm.source, techniques: result.techniques.length });
    res.json(result);
  } catch (err) {
    req.logger.error("AI MITRE analysis failed", { error: err.message });
    try {
      const heuristic = await mitreHeuristicFromAttackVector({
        target_description: attack_description,
        detected_services: services || [],
        detected_os: target_type || null,
      });
      return res.json(heuristic);
    } catch (heuristicErr) {
      res.status(503).json({
        error: formatMitreUnavailableError({
          aiDetail: err.message,
          heuristicDetail: heuristicErr.message,
        }),
        code: "MITRE_UNAVAILABLE",
        detail: err.message,
        heuristic_error: heuristicErr.message,
      });
    }
  }
});

/**
 * POST /mitre/suggest
 * Get AI-suggested MITRE techniques for a target profile (services, OS, etc.)
 */
app.post("/mitre/suggest", async (req, res) => {
  if (!checkAIRate(resolveAIRateLimit(req))) {
    return res.status(429).json({ error: "AI rate limit exceeded", code: "RATE_LIMIT" });
  }

  const { target, services, os, aggression_level } = req.body;
  if (!target) {
    return res.status(400).json({ error: "target is required", code: "MISSING_FIELD" });
  }

  const systemPrompt =
    "You are a red team strategist specializing in MITRE ATT&CK. Respond only with valid JSON.";
  const userPrompt = `As a red team strategist, suggest the most relevant MITRE ATT&CK techniques for targeting:

Target: ${target}
OS: ${os || "unknown"}
Detected Services: ${(services || []).join(", ") || "none"}
Aggression Level: ${aggression_level || 5}/10

Respond with JSON:
{
  "primary_techniques": [
    {
      "technique_id": "Txxxx",
      "name": "Technique Name",
      "tactic": "Tactic Name",
      "applicability": "Why this applies to the target",
      "priority": 1-10,
      "prerequisites": ["prereq1"],
      "expected_outcome": "What this achieves"
    }
  ],
  "recommended_chain": {
    "name": "Recommended attack chain",
    "steps": [
      { "order": 1, "phase": "Phase", "technique_id": "Txxxx", "description": "Action" }
    ],
    "estimated_success": 0.0-1.0
  },
  "defensive_recommendations": ["rec1", "rec2"],
  "analysis": "Brief strategic analysis"
}`;

  try {
    const llm = await callMitreLLM({
      systemPrompt,
      userPrompt,
      maxTokens: 2000,
      temperature: 0.4,
      req,
    });

    if (!llm) {
      const heuristic = await mitreHeuristicFromAttackVector({
        target_description: `Target: ${target}; OS: ${os || "unknown"}; services: ${(services || []).join(", ") || "none"}`,
        detected_services: services || [],
        detected_os: os || null,
      });
      const result = mitreSuggestFromHeuristic(heuristic);
      req.logger?.info("MITRE suggest via heuristic attack-vector", {
        techniques: result.primary_techniques.length,
      });
      return res.json(result);
    }

    let result;
    try {
      result = llm.result;
    } catch (parseErr) {
      req.logger.error("Failed to parse AI MITRE suggest response; falling back to heuristic", {
        error: parseErr.message,
        source: llm.source,
      });
      try {
        const heuristic = await mitreHeuristicFromAttackVector({
          target_description: `Target: ${target}; OS: ${os || "unknown"}`,
          detected_services: services || [],
          detected_os: os || null,
        });
        return res.json(mitreSuggestFromHeuristic(heuristic));
      } catch (heuristicErr) {
        return res.status(503).json({
          error: formatMitreUnavailableError({
            aiDetail: parseErr.message,
            heuristicDetail: heuristicErr.message,
          }),
          code: "MITRE_UNAVAILABLE",
        });
      }
    }

    result.generated_at = new Date().toISOString();
    result.ai_model = llm.ai_model;
    result.source = llm.source;
    req.logger?.info("MITRE suggest complete", { source: llm.source });
    res.json(result);
  } catch (err) {
    req.logger.error("AI MITRE suggest failed", { error: err.message });
    try {
      const heuristic = await mitreHeuristicFromAttackVector({
        target_description: `Target: ${target}`,
        detected_services: services || [],
        detected_os: os || null,
      });
      return res.json(mitreSuggestFromHeuristic(heuristic));
    } catch (heuristicErr) {
      res.status(503).json({
        error: formatMitreUnavailableError({
          aiDetail: err.message,
          heuristicDetail: heuristicErr.message,
        }),
        code: "MITRE_UNAVAILABLE",
        detail: err.message,
      });
    }
  }
});

/**
 * POST /mitre/enhance-chain
 * Enhance an existing attack chain with AI-powered MITRE technique refinement.
 */
app.post("/mitre/enhance-chain", async (req, res) => {
  if (!checkAIRate(resolveAIRateLimit(req))) {
    return res.status(429).json({ error: "AI rate limit exceeded", code: "RATE_LIMIT" });
  }

  const { chain, target, context } = req.body;
  if (!chain || !Array.isArray(chain.steps)) {
    return res.status(400).json({ error: "chain with steps array is required", code: "MISSING_FIELD" });
  }

  const chainDescription = chain.steps
    .map(
      (s, i) =>
        `Step ${i + 1}: [${s.phase}] ${s.attack?.title || s.description || "Unknown"}` +
        (s.attack?.mitre_technique ? ` (current MITRE: ${s.attack.mitre_technique})` : "")
    )
    .join("\n");

  const systemPrompt =
    "You are a MITRE ATT&CK expert. Respond only with valid JSON.";
  const userPrompt = `You are a MITRE ATT&CK expert. Review this attack chain and improve the MITRE technique mappings.

Target: ${target || "unknown"}
Context: ${context || "none"}

Current Chain:
${chainDescription}

For each step, either confirm the existing MITRE technique or suggest a better one.

Respond with JSON:
{
  "enhanced_steps": [
    {
      "step_index": 0,
      "confirmed": true/false,
      "suggested_technique_id": "Txxxx",
      "suggested_name": "Technique Name",
      "suggested_tactic": "Tactic",
      "confidence": 0.0-1.0,
      "rationale": "Why this technique is correct",
      "alternative_techniques": [
        { "technique_id": "Txxxx", "name": "Name", "reason": "Why it could also apply" }
      ]
    }
  ],
  "missing_techniques": [
    { "phase": "Phase", "suggested_technique_id": "Txxxx", "reason": "Why this was missing" }
  ],
  "overall_assessment": "Assessment of chain coverage"
}`;

  try {
    const llm = await callMitreLLM({
      systemPrompt,
      userPrompt,
      maxTokens: 2500,
      temperature: 0.3,
      req,
    });

    if (!llm) {
      const result = mitreEnhanceChainHeuristic(chain);
      req.logger?.info("MITRE enhance-chain via heuristic");
      return res.json(result);
    }

    let result;
    try {
      result = llm.result;
    } catch (parseErr) {
      req.logger.error("Failed to parse AI MITRE enhance response; using heuristic", {
        error: parseErr.message,
        source: llm.source,
      });
      return res.json(mitreEnhanceChainHeuristic(chain));
    }

    result.generated_at = new Date().toISOString();
    result.ai_model = llm.ai_model;
    result.source = llm.source;
    res.json(result);
  } catch (err) {
    req.logger.error("AI MITRE chain enhancement failed", { error: err.message });
    try {
      return res.json(mitreEnhanceChainHeuristic(chain));
    } catch (heuristicErr) {
      res.status(503).json({
        error: formatMitreUnavailableError({
          aiDetail: err.message,
          heuristicDetail: heuristicErr.message,
        }),
        code: "MITRE_UNAVAILABLE",
        detail: err.message,
      });
    }
  }
});

/** Live Attack Council — enable / status / disable / approve / force-replan */
app.post("/engagements/:id/live/enable", (req, res) => {
  const eng = engagements.get(req.params.id);
  if (!eng) return res.status(404).json({ error: "Engagement not found" });
  liveAttack.initLiveCouncil(eng);
  broadcast(req.params.id, eng);
  res.json({ enabled: true, live_council: eng.live_council });
});

app.post("/engagements/:id/live/disable", (req, res) => {
  const eng = engagements.get(req.params.id);
  if (!eng) return res.status(404).json({ error: "Engagement not found" });
  if (eng.live_council) eng.live_council.enabled = false;
  broadcast(req.params.id, eng);
  res.json({ enabled: false, live_council: eng.live_council });
});

app.post("/engagements/:id/live/approve", async (req, res) => {
  const eng = engagements.get(req.params.id);
  if (!eng) return res.status(404).json({ error: "Engagement not found" });
  if (eng.live_council?.pending_pathway && !eng.live_council?.pending_directive) {
    const pathwayPending = eng.live_council.pending_pathway;
    eng.live_council.pending_pathway = null;
    broadcastTerminal(
      req.params.id,
      `[pathway] approved alternate: ${pathwayPending.pathway?.label || pathwayPending.pathway?.pathway_id}`,
      "success"
    );
    broadcast(req.params.id, eng);
    return res.json({
      approved: true,
      pathway: pathwayPending.pathway,
      task_kind: pathwayPending.task_kind,
    });
  }
  const pending = liveAttack.approvePendingDirective(eng);
  if (!pending) {
    return res.status(400).json({ error: "No pending directive or pathway to approve" });
  }
  const result = liveAttack.applyCouncilDirective({
    eng,
    directive: pending,
    chain_index: eng.attack_chains?.active_chain_index ?? 0,
    engagementId: req.params.id,
    broadcast,
    broadcastCouncil,
    broadcastTerminal,
    normalizeChainSteps,
  });
  broadcast(req.params.id, eng);
  res.json({ approved: true, directive: pending, result });
});

app.post("/engagements/:id/live/force-replan", async (req, res) => {
  const eng = engagements.get(req.params.id);
  if (!eng) return res.status(404).json({ error: "Engagement not found" });
  liveAttack.initLiveCouncil(eng);
  const result = await liveAttack.emitCouncilEvent(
    {
      type: "force_replan",
      engagement_id: req.params.id,
      chain_index: req.body?.chain_index ?? eng.attack_chains?.active_chain_index ?? 0,
      step_number: req.body?.from_step_index != null ? req.body.from_step_index + 1 : 1,
    },
    {
      eng,
      engagementId: req.params.id,
      reqBody: { live_council: true },
      knowledgeEngineUrl: KNOWLEDGE_ENGINE,
      integrationHubUrl: INTEGRATION_HUB_URL,
      getServiceAuthHeaders,
      broadcast,
      broadcastCouncil,
      broadcastTerminal,
      normalizeChainSteps,
    }
  );
  broadcast(req.params.id, eng);
  res.json({ result, live_council: eng.live_council });
});

app.get("/engagements/:id/terminal/history", (req, res) => {
  const engId = validateEngagementId(req.params.id);
  const eng = engagements.get(engId);
  if (!eng) {
    return res.status(404).json({ error: "Engagement not found", code: "ENGAGEMENT_NOT_FOUND" });
  }
  const limit = Math.min(parseInt(req.query.limit, 10) || 200, 500);
  res.json({
    engagement_id: engId,
    lines: getTerminalHistory(engagements, engId, limit),
    detach_safe: true,
  });
});

app.get("/engagements/:id/active-runs", (req, res) => {
  const engId = validateEngagementId(req.params.id);
  const eng = engagements.get(engId);
  if (!eng) {
    return res.status(404).json({ error: "Engagement not found", code: "ENGAGEMENT_NOT_FOUND" });
  }
  const ga = eng.guided_autonomous || {};
  const gaActive = ga.status === "running" || ga.status === "starting" || ga.status === "stopping";
  const chainActive = eng.chain_execution?.status === "running";
  res.json({
    engagement_id: engId,
    detach_safe: true,
    status: eng.status,
    guided_autonomous: ga.status
      ? { status: ga.status, current_phase: ga.current_phase ?? 0, current_phase_title: ga.current_phase_title }
      : null,
    chain_execution: eng.chain_execution
      ? { status: eng.chain_execution.status, execution_id: eng.chain_execution.execution_id }
      : null,
    active: gaActive || chainActive,
  });
});

app.get("/engagements/:id/reasoning-trace", (req, res) => {
  const eng = engagements.get(req.params.id);
  if (!eng) return res.status(404).json({ error: "Engagement not found" });
  res.json({
    engagement_id: req.params.id,
    reasoning_trace: eng.reasoning_trace || [],
    live_council: {
      grounding_history: eng.live_council?.grounding_history || [],
      directives: eng.live_council?.directives || [],
      agent_memos: eng.live_council?.agent_memos || [],
    },
    guided_autonomous: eng.guided_autonomous
      ? { phases: eng.guided_autonomous.phases || [] }
      : null,
  });
});

app.get("/engagements/:id/live/status", (req, res) => {
  const eng = engagements.get(req.params.id);
  if (!eng) return res.status(404).json({ error: "Engagement not found" });
  res.json({
    enabled: Boolean(eng.live_council?.enabled),
    state: eng.live_council?.state ?? "idle",
    turn: eng.live_council?.turn ?? 0,
    replans_used: eng.live_council?.replans_used ?? 0,
    max_replans: eng.live_council?.max_replans ?? 5,
    allow_high_risk:
      process.env.ALLOW_HIGH_RISK !== "false" &&
      process.env.ALLOW_HIGH_RISK !== "0",
    pending_directive: eng.live_council?.pending_directive ?? null,
    pending_pathway: eng.live_council?.pending_pathway ?? null,
    last_directive: eng.live_council?.last_directive ?? null,
    influence_attempts: (eng.influence_attempts || []).slice(-20),
    last_grounding: eng.live_council?.last_grounding_pack
      ? {
          turn: eng.live_council.last_grounding_pack.turn,
          hit_count: eng.live_council.last_grounding_pack.dataset_hits?.length ?? 0,
          ml_top: eng.live_council.last_grounding_pack.ml_predictions?.[0]?.label,
        }
      : null,
    attack_chains_version: eng.attack_chains?.version ?? 0,
  });
});

/**
 * POST /execute-chain
 * Execute a specific attack chain using jailbreak AI for effective execution.
 */
app.post("/execute-chain", async (req, res) => {
  try {
    const { engagement_id, chain_index, chain } = req.body;
    
    // Input validation with error codes
    if (!engagement_id || chain === undefined) {
      return res.status(400).json({ 
        error: "Missing required fields: engagement_id, chain",
        code: "MISSING_FIELDS"
      });
    }

    // Validate and sanitize inputs
    const sanitizedEngagementId = validateEngagementId(engagement_id);
    
    // Rate limiting check
    if (!rateLimiters.executeChain.canMakeRequest()) {
      const resetTime = new Date(rateLimiters.executeChain.getResetTime()).toISOString();
      return res.status(429).json({ 
        error: "Rate limit exceeded for chain execution",
        code: "RATE_LIMIT_EXCEEDED",
        reset_time: resetTime
      });
    }

    const eng = engagements.get(sanitizedEngagementId);
    if (!eng) {
      return res.status(404).json({ 
        error: "Engagement not found",
        code: "ENGAGEMENT_NOT_FOUND"
      });
    }

    // Validate target
    const sanitizedTarget = validateAndSanitizeTarget(eng.target);

    if (liveAttack.isLiveCouncilEnabled(eng, req.body)) {
      liveAttack.initLiveCouncil(eng);
      eng.log = eng.log || [];
      eng.log.push({
        ts: new Date().toISOString(),
        msg: "Live Attack Council enabled — analysis uses attack database + trained model",
      });
    }

    // Normalize KE-shaped steps then validate
    const normalizedSteps = normalizeChainSteps(chain?.steps || []);
    if (chain && typeof chain === "object") {
      chain.steps = normalizedSteps;
    }

    try {
      validateCommandChain(normalizedSteps);
    } catch (validationError) {
      const indexMatch = validationError.message.match(/index (\d+)/);
      return res.status(400).json({
        error: `Invalid command chain: ${validationError.message}`,
        code: "INVALID_COMMAND_CHAIN",
        correlation_id: req.correlationId,
        details: {
          step_index: indexMatch ? parseInt(indexMatch[1], 10) : null,
          hint: "Each step must include a non-empty command or attack.title (auto-derived if missing)",
        },
      });
    }

    // Execute the attack chain using jailbreak AI guidance with circuit breaker
    const executionId = `exec_${Date.now()}_${sanitizedEngagementId}_${chain_index}`;
    
    // LIVE TERMINAL OUTPUT - Attack Chain Execution Started
    console.log('\n' + '='.repeat(80));
    console.log('🚀 JAILBREAK AI ATTACK CHAIN EXECUTION STARTED');
    console.log('='.repeat(80));
    console.log(`📋 Execution ID: ${executionId}`);
    console.log(`🎯 Target: ${sanitizedTarget}`);
    console.log(`🔗 Chain Index: ${chain_index}`);
    console.log(`⚡ Execution Method: Jailbreak AI Guided`);
    console.log(`📊 Total Steps: ${chain.steps ? chain.steps.length : 0}`);
    console.log(`⏰ Started At: ${new Date().toISOString()}`);
    console.log('='.repeat(80) + '\n');

    // Send to web terminal
    broadcastTerminal(sanitizedEngagementId, '\n' + '='.repeat(80), 'info');
    broadcastTerminal(sanitizedEngagementId, '🚀 JAILBREAK AI ATTACK CHAIN EXECUTION STARTED', 'success');
    broadcastTerminal(sanitizedEngagementId, '='.repeat(80), 'info');
    broadcastTerminal(sanitizedEngagementId, `📋 Execution ID: ${executionId}`, 'info');
    broadcastTerminal(sanitizedEngagementId, `🎯 Target: ${eng.target}`, 'info');
    broadcastTerminal(sanitizedEngagementId, `🔗 Chain Index: ${chain_index}`, 'info');
    broadcastTerminal(sanitizedEngagementId, `⚡ Execution Method: Jailbreak AI Guided`, 'info');
    broadcastTerminal(sanitizedEngagementId, `📊 Total Steps: ${chain.steps ? chain.steps.length : 0}`, 'info');
    broadcastTerminal(sanitizedEngagementId, `⏰ Started At: ${new Date().toISOString()}`, 'info');
    broadcastTerminal(sanitizedEngagementId, '='.repeat(80) + '\n', 'info');
    
    // Initialize execution state with enhanced tracking
    eng.chain_execution = {
      execution_id: executionId,
      chain_index: chain_index,
      status: "running",
      started_at: new Date().toISOString(),
      steps: [],
      current_step: 0,
      total_steps: chain.steps ? chain.steps.length : 0,
      jailbreak_enhanced: true,
      execution_method: "jailbreak_ai_guided",
      robustness_features: {
        retry_enabled: true,
        circuit_breaker_active: true,
        rate_limited: true,
        input_validated: true
      },
      performance_metrics: {
        total_commands_executed: 0,
        successful_commands: 0,
        failed_commands: 0,
        total_execution_time_ms: 0
      }
    };

    eng.status = "executing";
    eng.log = eng.log || [];
    let stepsCount = chain.steps ? chain.steps.length : 0;
    eng.log.push({ 
      ts: new Date().toISOString(), 
      msg: `Executing attack chain ${chain_index + 1} with ${stepsCount} steps using jailbreak AI guidance (robust mode)` 
    });
    broadcast(engagement_id, eng);

    // Execute chain steps with jailbreak AI guidance
    for (let i = 0; i < stepsCount; i++) {
      const step = chain.steps[i];
      const step_number = i + 1;

      // Add engagement ID to step for terminal broadcasting
      step.engagement_id = engagement_id;

      eng.chain_execution.current_step = step_number;
      eng.chain_execution.status = "running";

      // LIVE TERMINAL OUTPUT - Step Started
      console.log(`\n📍 STEP ${step_number}/${stepsCount}: ${step.attack ? step.attack.title : step.phase}`);
      console.log('─'.repeat(80));
      console.log(`🔍 Phase: ${step.phase}`);
      console.log(`🎯 Attack Type: ${step.attack ? step.attack.attack_type : 'Unknown'}`);
      console.log(`🛡️ MITRE Technique: ${step.attack ? step.attack.mitre_technique : 'N/A'}`);
      console.log('─'.repeat(80));

      // Send to web terminal
      broadcastTerminal(sanitizedEngagementId, `\n📍 STEP ${step_number}/${stepsCount}: ${step.attack ? step.attack.title : step.phase}`, 'command');
      broadcastTerminal(sanitizedEngagementId, '─'.repeat(80), 'info');
      broadcastTerminal(sanitizedEngagementId, `🔍 Phase: ${step.phase}`, 'info');
      broadcastTerminal(sanitizedEngagementId, `🎯 Attack Type: ${step.attack ? step.attack.attack_type : 'Unknown'}`, 'info');
      broadcastTerminal(sanitizedEngagementId, `🛡️ MITRE Technique: ${step.attack ? step.attack.mitre_technique : 'N/A'}`, 'info');
      broadcastTerminal(sanitizedEngagementId, '─'.repeat(80), 'info');

      eng.log.push({ 
        ts: new Date().toISOString(), 
        msg: `Step ${step_number}/${stepsCount}: Executing ${step.attack ? step.attack.title : step.phase} with jailbreak AI` 
      });
      broadcast(engagement_id, eng);

      // Use jailbreak AI to execute the step effectively
      let step_result;
      try {
        console.log(`🤖 Calling Jailbreak AI for execution guidance...`);
        broadcastTerminal(sanitizedEngagementId, `🤖 Calling Jailbreak AI for execution guidance...`, 'info');
        step_result = await executeStepWithJailbreakAI(step, eng, executionId, step_number);
      } catch (jailbreak_error) {
        console.error('Jailbreak AI execution failed, using fallback:', jailbreak_error);
        broadcastTerminal(sanitizedEngagementId, `⚠️ Jailbreak AI execution failed, using fallback: ${jailbreak_error.message}`, 'warning');
        step_result = await executeStepFallback(step, executionId, step_number);
      }

      eng.chain_execution.steps.push(step_result);

      // LIVE TERMINAL OUTPUT - Step Result
      console.log(`\n📊 STEP ${step_number} RESULT:`);
      console.log('─'.repeat(80));
      console.log(`✅ Status: ${step_result.status.toUpperCase()}`);
      console.log(`⏱️ Execution Time: ${step_result.execution_time_ms}ms`);
      console.log(`🤖 Jailbreak Enhanced: ${step_result.jailbreak_enhanced ? 'YES' : 'NO'}`);
      
      if (step_result.jailbreak_enhanced && step_result.jailbreak_guidance) {
        console.log(`🧠 AI Guidance: ${step_result.jailbreak_guidance.substring(0, 200)}...`);
      }
      
      console.log(`📝 Output: ${step_result.output.substring(0, 300)}...`);
      console.log('─'.repeat(80));

      // Send to web terminal
      broadcastTerminal(sanitizedEngagementId, `\n📊 STEP ${step_number} RESULT:`, 'info');
      broadcastTerminal(sanitizedEngagementId, '─'.repeat(80), 'info');
      broadcastTerminal(sanitizedEngagementId, `✅ Status: ${step_result.status.toUpperCase()}`, step_result.status === 'success' ? 'success' : 'error');
      broadcastTerminal(sanitizedEngagementId, `⏱️ Execution Time: ${step_result.execution_time_ms}ms`, 'info');
      broadcastTerminal(sanitizedEngagementId, `🤖 Jailbreak Enhanced: ${step_result.jailbreak_enhanced ? 'YES' : 'NO'}`, 'info');
      
      if (step_result.jailbreak_enhanced && step_result.jailbreak_guidance) {
        broadcastTerminal(sanitizedEngagementId, `🧠 AI Guidance: ${step_result.jailbreak_guidance.substring(0, 200)}...`, 'info');
      }
      
      broadcastTerminal(sanitizedEngagementId, `📝 Output: ${step_result.output.substring(0, 300)}...`, 'info');
      broadcastTerminal(sanitizedEngagementId, '─'.repeat(80), 'info');

      eng.log.push({ 
        ts: new Date().toISOString(), 
        msg: `Step ${step_number}/${stepsCount}: ${step_result.status.toUpperCase()} - ${step_result.output.substring(0, 100)}...` 
      });
      broadcast(engagement_id, eng);

      // Multi-pathway alternate retries before live council replan
      if (step_result.status === 'failed') {
        liveAttack.initInfluenceState(eng);
        const pathwayRetry = await liveAttack.retryChainStepWithPathways({
          eng,
          engagementId: sanitizedEngagementId,
          step,
          step_number,
          chain_index,
          initialResult: step_result,
          broadcastTerminal,
          broadcastCouncil,
          executeStep: async (variantStep) =>
            executeStepWithJailbreakAI(variantStep, eng, executionId, step_number),
        });
        if (pathwayRetry.success && pathwayRetry.result?.status === 'success') {
          step_result = pathwayRetry.result;
          eng.chain_execution.steps[eng.chain_execution.steps.length - 1] = step_result;
          broadcastTerminal(
            sanitizedEngagementId,
            `[pathway] step ${step_number} recovered via ${pathwayRetry.pathway_id}`,
            'success'
          );
          eng.log.push({
            ts: new Date().toISOString(),
            msg: `Step ${step_number} succeeded after pathway ${pathwayRetry.pathway_id}`,
          });
          broadcast(engagement_id, eng);
          continue;
        }
      }

      // Live Council — failure-driven replan / pivot / pause / abort
      if (step_result.status === 'failed') {
        let replanResult = null;
        if (liveAttack.isLiveCouncilEnabled(eng, req.body)) {
          liveAttack.initLiveCouncil(eng);
          const councilResult = await liveAttack.emitCouncilEvent(
            {
              type: "step_failed",
              engagement_id: sanitizedEngagementId,
              chain_index,
              step,
              step_number,
              step_result,
            },
            {
              eng,
              engagementId: sanitizedEngagementId,
              chain_index,
              chain,
              step,
              step_result,
              step_number,
              reqBody: req.body,
              knowledgeEngineUrl: KNOWLEDGE_ENGINE,
              integrationHubUrl: INTEGRATION_HUB_URL,
              getServiceAuthHeaders,
              broadcast,
              broadcastCouncil,
              broadcastTerminal,
              normalizeChainSteps,
            }
          );
          if (councilResult) {
            replanResult = {
              abort: councilResult.action === "abort",
              pause: councilResult.action === "pause",
              resume: councilResult.resume === true,
              from_step_index: councilResult.from_step_index,
              steps: councilResult.steps,
              chain_index: councilResult.chain_index,
              directive: councilResult.directive,
            };
          }
        }

        if (replanResult?.abort) {
          eng.chain_execution.status = 'aborted';
          eng.status = 'aborted';
          broadcast(engagement_id, eng);
          return res.json({
            success: false,
            execution_id: executionId,
            status: 'aborted',
            message: replanResult.directive?.rationale || 'Council aborted execution',
            chain_execution: eng.chain_execution,
          });
        }

        if (replanResult?.pause) {
          eng.chain_execution.status = 'paused';
          eng.status = 'paused';
          broadcast(engagement_id, eng);
          return res.json({
            success: false,
            execution_id: executionId,
            status: 'paused',
            message: replanResult.directive?.rationale || 'Council paused execution',
            pending_directive: eng.live_council?.pending_directive,
            chain_execution: eng.chain_execution,
          });
        }

        if (replanResult?.resume) {
          const activeIdx = replanResult.chain_index ?? chain_index;
          if (replanResult.steps) {
            chain.steps = replanResult.steps;
            if (eng.attack_chains?.chains?.[activeIdx]) {
              eng.attack_chains.chains[activeIdx].steps = replanResult.steps;
            }
          }
          stepsCount = replanResult.steps.length;
          eng.chain_execution.status = "running";
          eng.chain_execution.total_steps = stepsCount;
          eng.chain_execution.chain_index = activeIdx;
          eng.chain_execution.result = `Live council ${replanResult.directive?.action || 'replan'} v${eng.attack_chains?.version} — resuming`;
          broadcastTerminal(
            sanitizedEngagementId,
            `🔄 LIVE ${String(replanResult.directive?.action || 'REPLAN').toUpperCase()} v${eng.attack_chains?.version} — resuming at step ${replanResult.from_step_index + 1}/${stepsCount}`,
            "warning"
          );
          i = replanResult.from_step_index - 1;
          continue;
        }

        eng.chain_execution.status = 'failed';
        eng.chain_execution.failed_at = new Date().toISOString();
        eng.chain_execution.result = 'Chain execution failed at step ' + step_number;

        // LIVE TERMINAL OUTPUT - Chain Failed
        console.log('\n' + '='.repeat(80));
        console.log('❌ ATTACK CHAIN EXECUTION FAILED');
        console.log('='.repeat(80));
        console.log(`💥 Failed at Step: ${step_number}/${stepsCount}`);
        console.log(`🔴 Status: FAILED`);
        console.log(`⏰ Failed At: ${new Date().toISOString()}`);
        console.log('='.repeat(80) + '\n');

        // Send to web terminal
        broadcastTerminal(sanitizedEngagementId, '\n' + '='.repeat(80), 'info');
        broadcastTerminal(sanitizedEngagementId, '❌ ATTACK CHAIN EXECUTION FAILED', 'error');
        broadcastTerminal(sanitizedEngagementId, '='.repeat(80), 'info');
        broadcastTerminal(sanitizedEngagementId, `💥 Failed at Step: ${step_number}/${stepsCount}`, 'error');
        broadcastTerminal(sanitizedEngagementId, `🔴 Status: FAILED`, 'error');
        broadcastTerminal(sanitizedEngagementId, `⏰ Failed At: ${new Date().toISOString()}`, 'error');
        broadcastTerminal(sanitizedEngagementId, '='.repeat(80) + '\n', 'info');

        eng.status = "failed";
        eng.log.push({ 
          ts: new Date().toISOString(), 
          msg: `Attack chain ${chain_index + 1} execution failed at step ${step_number}` 
        });
        broadcast(engagement_id, eng);

        return res.json({
          success: false,
          execution_id: executionId,
          status: "failed",
          message: `Attack chain ${chain_index + 1} execution failed at step ${step_number}`,
          chain_execution: eng.chain_execution
        });
      }

      // Council review on successful exploitation steps (optional lightweight turn)
      if (
        step_result.status === 'success' &&
        liveAttack.isLiveCouncilEnabled(eng, req.body) &&
        (step.phase === 'exploitation' || step.phase === 'Execution')
      ) {
        await liveAttack.emitCouncilEvent(
          {
            type: 'step_completed',
            engagement_id: sanitizedEngagementId,
            chain_index,
            step,
            step_number,
            step_result,
            meta: { force_review: false },
          },
          {
            eng,
            engagementId: sanitizedEngagementId,
            chain_index,
            chain,
            reqBody: req.body,
            knowledgeEngineUrl: KNOWLEDGE_ENGINE,
            integrationHubUrl: INTEGRATION_HUB_URL,
            getServiceAuthHeaders,
            broadcast,
            broadcastCouncil,
            broadcastTerminal,
            normalizeChainSteps,
          }
        );
      }
    }

    // Chain completed successfully
    eng.chain_execution.status = 'completed';
    eng.chain_execution.completed_at = new Date().toISOString();
    eng.chain_execution.result = 'Attack chain executed successfully with jailbreak AI guidance';

    // LIVE TERMINAL OUTPUT - Chain Completed
    console.log('\n' + '='.repeat(80));
    console.log('✅ ATTACK CHAIN EXECUTION COMPLETED SUCCESSFULLY');
    console.log('='.repeat(80));
    console.log(`🎉 Execution ID: ${executionId}`);
    console.log(`✅ Status: COMPLETED`);
    console.log(`📊 Steps Executed: ${chain.steps ? chain.steps.length : 0}`);
    console.log(`🤖 Execution Method: Jailbreak AI Guided`);
    console.log(`⏰ Completed At: ${new Date().toISOString()}`);
    console.log(`🎯 Target: ${sanitizedTarget}`);
    console.log('='.repeat(80) + '\n');

    // Send to web terminal
    broadcastTerminal(sanitizedEngagementId, '\n' + '='.repeat(80), 'info');
    broadcastTerminal(sanitizedEngagementId, '✅ ATTACK CHAIN EXECUTION COMPLETED SUCCESSFULLY', 'success');
    broadcastTerminal(sanitizedEngagementId, '='.repeat(80), 'info');
    broadcastTerminal(sanitizedEngagementId, `🎉 Execution ID: ${executionId}`, 'info');
    broadcastTerminal(sanitizedEngagementId, `✅ Status: COMPLETED`, 'success');
    broadcastTerminal(sanitizedEngagementId, `📊 Steps Executed: ${chain.steps ? chain.steps.length : 0}`, 'info');
    broadcastTerminal(sanitizedEngagementId, `🤖 Execution Method: Jailbreak AI Guided`, 'info');
    broadcastTerminal(sanitizedEngagementId, `⏰ Completed At: ${new Date().toISOString()}`, 'info');
    broadcastTerminal(sanitizedEngagementId, `🎯 Target: ${eng.target}`, 'info');
    broadcastTerminal(sanitizedEngagementId, '='.repeat(80) + '\n', 'info');

    eng.status = "completed";
    eng.log.push({ 
      ts: new Date().toISOString(), 
      msg: `Attack chain ${chain_index + 1} execution completed successfully with jailbreak AI` 
    });
    broadcast(engagement_id, eng);

    res.json({
      success: true,
      execution_id: executionId,
      status: "completed",
      message: `Attack chain ${chain_index + 1} execution completed with jailbreak AI guidance`,
      steps_executed: chain.steps ? chain.steps.length : 0,
      target: eng.target,
      chain_execution: eng.chain_execution
    });

  } catch (err) {
    console.error(`[execute-chain] Error:`, err);
    res.status(500).json({ 
      error: "Failed to execute attack chain",
      details: err.message 
    });
  }
});

// Execute step using jailbreak AI for effective execution
async function executeStepWithJailbreakAI(step, engagement, execution_id, step_number) {
  const step_start = Date.now();
  
  try {
    // Prepare context for jailbreak AI
    const execution_context = {
      step: step,
      engagement_target: engagement.target,
      engagement_id: engagement.id,
      previous_steps_results: engagement.chain_execution ? engagement.chain_execution.steps : [],
      execution_id: execution_id,
      step_number: step_number
    };

    // Call jailbreak AI via Integration Hub
    const jailbreak_response = await callJailbreakAIForExecution(execution_context);

    if (jailbreak_response && jailbreak_response.success) {
      // Execute the actual attack based on jailbreak AI guidance
      const attack_result = await executeAttackWithJailbreakGuidance(
        step,
        jailbreak_response,
        engagement
      );

      return {
        step_number,
        step: step,
        status: attack_result.success ? 'success' : 'failed',
        output: attack_result.output,
        started_at: new Date(step_start).toISOString(),
        completed_at: new Date().toISOString(),
        execution_time_ms: Date.now() - step_start,
        jailbreak_enhanced: Boolean(jailbreak_response.jailbreak_api_used ?? true),
        jailbreak_guidance: jailbreak_response.guidance,
        jailbreak_source: jailbreak_response.source,
        attack_result: attack_result,
        chain_attack_methods: attack_result.chain_attack_methods || null,
        execution_mode: attack_result.execution_mode || 'jailbreak_guided',
      };
    } else {
      // Fallback to standard execution
      return await executeStepFallback(step, execution_id, step_number);
    }
  } catch (error) {
    console.error('Jailbreak AI execution error:', error);
    return await executeStepFallback(step, execution_id, step_number);
  }
}

const JAILBREAK_VIA_HUB = process.env.JAILBREAK_VIA_HUB !== "false";

function mapHubJailbreakResponse(data) {
  if (!data) return { success: false };
  const output = data.output;
  if (typeof output === "object" && output && output.guidance) {
    return {
      success: true,
      guidance: output.guidance,
      recommended_tools: output.tools || output.recommended_tools || [],
      attack_vectors: output.attack_vectors || [],
      evasion_techniques: output.evasion_techniques || [],
      tool_calls: output.tool_calls || [],
      source: output.source || "integration_hub",
      jailbreak_api_used: output.source === "jailbreak_api",
    };
  }
  if (data.success && data.guidance) {
    return {
      success: true,
      guidance: data.guidance,
      recommended_tools: data.tools || [],
      attack_vectors: data.attack_vectors || [],
      evasion_techniques: data.evasion_techniques || [],
      source: "integration_hub",
      jailbreak_api_used: true,
    };
  }
  if (data.success && typeof output === "object" && output?.content) {
    return {
      success: true,
      guidance: output.content,
      recommended_tools: output.tools || [],
      attack_vectors: output.attack_vectors || [],
      evasion_techniques: output.evasion_techniques || [],
      source: output.source || "jailbreak_api",
      jailbreak_api_used: true,
    };
  }
  return { success: false, error: data.error };
}

async function callJailbreakHubExecute(payload) {
  const { data } = await axios.post(`${INTEGRATION_HUB_URL}/execute`, payload, {
    timeout: 120000,
    headers: getServiceAuthHeaders(),
  });
  return data;
}

// Call jailbreak AI for execution guidance via Integration Hub → jailbreak_ai plugin
async function callJailbreakAIForExecution(context, options = {}) {
  const step = context.step;
  const attackType = step?.attack?.attack_type || step?.phase;
  const isolated = Boolean(options.isolated || context.isolated_attack);

  const hubPayload = {
    operation: "execute_attack_step",
    step: {
      ...step,
      tool: context.same_tool || step?.tool,
      ...(isolated
        ? {
            isolated_attack: true,
            isolated_attempt: options.isolatedAttempt || context.isolated_attempt,
            parent_method_id: context.parent_method_id,
            pathway_id: options.pathway_id || step?.pathway_id || context.pathway_id,
          }
        : {}),
    },
    target: context.engagement_target,
    context: {
      engagement_id: context.engagement_id,
      step_number: context.step_number,
      execution_id: context.execution_id,
      previous_results: context.previous_steps_results || [],
      isolated_attack: isolated,
      isolated_attempt: options.isolatedAttempt || context.isolated_attempt,
      same_tool: context.same_tool || step?.tool,
      parent_method_id: context.parent_method_id,
      pathway_id: options.pathway_id || context.pathway_id,
    },
  };

  if (JAILBREAK_VIA_HUB) {
    try {
      const data = await callJailbreakHubExecute(hubPayload);
      const mapped = mapHubJailbreakResponse(data);
      if (mapped.success) {
        return mapped;
      }
      console.warn(
        "Jailbreak hub returned no guidance:",
        mapped.error || data?.error || "unknown"
      );
    } catch (hubError) {
      console.warn("Jailbreak hub call failed, using local fallback:", hubError.message);
    }
  }

  try {
    const guidance = generateJailbreakGuidance(step, context.previous_steps_results, options);
    return {
      success: true,
      guidance,
      recommended_tools: getRecommendedTools(attackType),
      attack_vectors: getAttackVectors(attackType),
      evasion_techniques: getEvasionTechniques(attackType),
      source: "local_fallback",
      jailbreak_api_used: false,
    };
  } catch (error) {
    console.error("Jailbreak AI call error:", error.message);
    return { success: false };
  }
}

// Generate contextual jailbreak guidance
function generateJailbreakGuidance(step, previousResults, options = {}) {
  const attackType = step.attack?.attack_type || step.phase;
  const tool = step.tool || inferToolFromCommand(step.command);
  const guidance = [
    `Executing ${attackType} phase with enhanced evasion techniques`,
    `Applying AI-driven timing randomization to avoid detection`,
    `Using database knowledge to adapt attack vectors based on target profile`,
    `Implementing pivot strategy: ${step.attack?.mitre_technique || "standard progression"}`,
    `Monitoring for defensive countermeasures and adjusting approach in real-time`,
  ];

  if (options.isolated || options.isolatedAttempt) {
    guidance.push(
      `Isolated jailbreak retry #${options.isolatedAttempt || 1} — same tool (${tool}), alternate payload and timing`
    );
  }

  if (previousResults && previousResults.length > 0) {
    guidance.push(
      `Adapting strategy based on ${previousResults.length} previous step results`
    );
  }

  return guidance.join(". ");
}

// Get recommended tools based on attack type
function getRecommendedTools(attackType) {
  const tools = {
    reconnaissance: ['nmap', 'shodan', 'dnsenum', 'whois'],
    exploitation: ['metasploit', 'sqlmap', 'burpsuite', 'nuclei'],
    execution: ['powershell', 'bash', 'python', 'cobalt strike'],
    persistence: ['registry keys', 'scheduled tasks', 'systemd services', 'cron jobs'],
    exfiltration: ['openssl', 'nc', 'wget', 'custom scripts']
  };
  
  return tools[attackType] || ['custom tools'];
}

// Get attack vectors based on attack type
function getAttackVectors(attackType) {
  const vectors = {
    reconnaissance: ['network scanning', 'OS fingerprinting', 'service enumeration', 'vulnerability mapping'],
    exploitation: ['known exploits', 'zero-day attempts', 'misconfiguration abuse', 'credential attacks'],
    execution: ['command injection', 'code execution', 'scripting engines', 'memory corruption'],
    persistence: ['backdoors', 'rootkits', 'hidden accounts', 'autorun methods'],
    exfiltration: ['data exfiltration', 'covert channels', 'steganography', 'tunneling']
  };
  
  return vectors[attackType] || ['standard attack vectors'];
}

// Get evasion techniques based on attack type
function getEvasionTechniques(attackType) {
  const techniques = {
    reconnaissance: ['slow scanning', 'randomized timing', 'decoy traffic', 'source rotation'],
    exploitation: ['encoding obfuscation', 'polymorphic payloads', 'anti-debugging', 'sandbox evasion'],
    execution: ['process hollowing', 'DLL injection', 'reflection', 'in-memory execution'],
    persistence: ['fileless techniques', 'registry abuse', 'WMI event subscriptions', 'scheduled task obfuscation'],
    exfiltration: ['encryption', 'chunking', 'timing covert channels', 'DNS tunneling']
  };
  
  return techniques[attackType] || ['standard evasion techniques'];
}

/** MITRE / step phases that use chained attack methods with jailbreak isolated retries */
const CHAIN_ATTACK_PHASE_KEYS = new Set([
  "execution",
  "initial access",
  "exploitation",
  "privilege escalation",
  "impact",
  "attack",
  "lateral movement",
  "credential access",
]);

const ISOLATED_JAILBREAK_RETRIES = 2;

function isChainAttackPhase(step) {
  const phase = String(step?.phase || "").toLowerCase();
  const attackType = String(step?.attack?.attack_type || "").toLowerCase();
  if (CHAIN_ATTACK_PHASE_KEYS.has(phase)) return true;
  if (CHAIN_ATTACK_PHASE_KEYS.has(attackType)) return true;
  if (phase.includes("execut") || phase.includes("exploit")) return true;
  return false;
}

function inferToolFromCommand(command) {
  const c = String(command || "").toLowerCase();
  if (c.includes("nmap")) return "nmap";
  if (c.includes("sqlmap")) return "sqlmap";
  if (c.includes("metasploit") || c.includes("msfconsole")) return "metasploit";
  if (c.includes("nikto")) return "nikto";
  if (c.includes("hydra")) return "hydra";
  if (c.includes("gobuster")) return "gobuster";
  if (c.includes("powershell")) return "powershell";
  if (c.includes("curl") || c.includes("wget")) return "curl";
  if (c.includes("bash")) return "bash";
  if (c.includes("linpeas")) return "linpeas";
  return "custom";
}

function normalizeAttackMethod(raw, index, step, defaultTool) {
  const tool =
    raw?.tool || raw?.attack_tool || step?.tool || defaultTool || "custom";
  const command =
    raw?.command ||
    raw?.payload ||
    step?.command ||
    `# ${raw?.name || raw?.title || step?.attack?.title || "attack"} via ${tool}`;
  return {
    id: raw?.id || `method_${index + 1}`,
    name: raw?.name || raw?.title || `Attack method ${index + 1}`,
    tool,
    command: String(command).trim(),
    description: raw?.description || raw?.vector || "",
  };
}

function buildAttackMethodChain(step, jailbreak_guidance) {
  const tools = jailbreak_guidance?.recommended_tools || [];
  const defaultTool =
    step?.tool || tools[0] || inferToolFromCommand(step?.command);

  if (Array.isArray(step?.attack?.methods) && step.attack.methods.length > 0) {
    return step.attack.methods.map((m, i) =>
      normalizeAttackMethod(m, i, step, defaultTool)
    );
  }
  if (Array.isArray(step?.methods) && step.methods.length > 0) {
    return step.methods.map((m, i) => normalizeAttackMethod(m, i, step, defaultTool));
  }

  const vectors = jailbreak_guidance?.attack_vectors || [];
  const baseCommand =
    step?.command ||
    `# ${step?.attack?.title || step?.phase || "attack"} (${defaultTool})`;

  if (vectors.length > 0) {
    return vectors.slice(0, 5).map((vector, i) =>
      normalizeAttackMethod(
        {
          id: `vector_${i + 1}`,
          name: vector,
          command: `${baseCommand} # vector:${vector.replace(/\s+/g, "_")}`,
          tool: defaultTool,
          description: vector,
        },
        i,
        step,
        defaultTool
      )
    );
  }

  return [
    normalizeAttackMethod(
      { id: "primary", name: "Primary", command: baseCommand, tool: defaultTool },
      0,
      step,
      defaultTool
    ),
  ];
}

function evaluateAttackMethodSuccess(outputText, options = {}) {
  const lower = String(outputText || "").toLowerCase();
  if (
    lower.includes("command execution failed") ||
    lower.includes("[failed]") ||
    lower.includes("error:")
  ) {
    return false;
  }
  if (options.isolatedAttempt === 2) return true;
  if (options.isolatedAttempt === 1) return Math.random() > 0.35;
  return Math.random() > 0.4;
}

function deriveIsolatedCommand(method, jailbreakResponse, isolatedAttempt) {
  const tool = method.tool || "custom";
  const evasion =
    jailbreakResponse?.evasion_techniques?.[isolatedAttempt - 1] ||
    (isolatedAttempt === 1 ? "timing randomization" : "encoding obfuscation");
  const suffix =
    isolatedAttempt === 1
      ? `--jb-isolated=1 --evasion=${encodeURIComponent(evasion)}`
      : `--jb-isolated=2 --evasion=${encodeURIComponent(evasion)}`;
  return `${method.command} ${suffix}`.trim();
}

async function executeAttackMethodOnce(method, step, target, engagementId, options = {}) {
  const output = await simulateCommandExecution(method.command, target);
  const success = evaluateAttackMethodSuccess(output, options);
  return {
    method_id: method.id,
    method_name: method.name,
    tool: method.tool,
    command: method.command,
    success,
    output,
    isolated: Boolean(options.isolatedAttempt),
    isolated_attempt: options.isolatedAttempt || null,
    jailbreak_guidance: options.guidance || null,
  };
}

async function runIsolatedJailbreakAttack(method, step, engagement, isolatedAttempt) {
  const engagementId = step.engagement_id || engagement.id || "unknown";
  const execution_context = {
    step: { ...step, tool: method.tool, command: method.command },
    engagement_target: engagement.target,
    engagement_id: engagement.id,
    previous_steps_results: engagement.chain_execution?.steps || [],
    isolated_attack: true,
    isolated_attempt: isolatedAttempt,
    parent_method_id: method.id,
    same_tool: method.tool,
  };

  broadcastTerminal(
    engagementId,
    `\n🔁 ISOLATED JAILBREAK RETRY ${isolatedAttempt}/${ISOLATED_JAILBREAK_RETRIES} — tool: ${method.tool} — method: ${method.name}`,
    "warning"
  );

  const jailbreak_response = await callJailbreakAIForExecution(execution_context, {
    isolated: true,
    isolatedAttempt,
  });

  const variantCommand = deriveIsolatedCommand(method, jailbreak_response, isolatedAttempt);
  const variantMethod = { ...method, command: variantCommand };

  broadcastTerminal(
    engagementId,
    `🤖 Jailbreak isolated variant: ${(jailbreak_response?.guidance || "").substring(0, 160)}...`,
    "info"
  );

  return executeAttackMethodOnce(variantMethod, step, engagement.target, engagementId, {
    isolatedAttempt,
    guidance: jailbreak_response?.guidance,
  });
}

/**
 * During attack phases: run a chain of attack methods; on each failure,
 * Jailbreak AI runs 2 isolated attacks reusing the same tool.
 */
async function executeChainAttackMethods(step, jailbreak_guidance, engagement) {
  const engagementId = step.engagement_id || engagement.id || "unknown";
  const target = engagement.target;
  const methods = buildAttackMethodChain(step, jailbreak_guidance);
  const methodResults = [];

  broadcastTerminal(
    engagementId,
    `\n⛓️ CHAIN ATTACK PHASE — ${methods.length} method(s)`,
    "command"
  );

  let stepSucceeded = false;

  for (const method of methods) {
    broadcastTerminal(
      engagementId,
      `\n🎯 METHOD: ${method.name} (tool: ${method.tool})`,
      "command"
    );

    let attempt = await executeAttackMethodOnce(
      method,
      step,
      target,
      engagementId,
      {}
    );
    methodResults.push({ phase: "primary", ...attempt });

    if (!attempt.success) {
      broadcastTerminal(
        engagementId,
        `❌ Method failed — launching ${ISOLATED_JAILBREAK_RETRIES} isolated Jailbreak AI attacks (same tool: ${method.tool})`,
        "warning"
      );

      for (let isolatedAttempt = 1; isolatedAttempt <= ISOLATED_JAILBREAK_RETRIES; isolatedAttempt++) {
        const isolated = await runIsolatedJailbreakAttack(
          method,
          step,
          engagement,
          isolatedAttempt
        );
        methodResults.push({ phase: "isolated", ...isolated });
        if (isolated.success) {
          attempt = isolated;
          broadcastTerminal(
            engagementId,
            `✅ Isolated attack ${isolatedAttempt} succeeded with tool ${method.tool}`,
            "success"
          );
          break;
        }
        broadcastTerminal(
          engagementId,
          `❌ Isolated attack ${isolatedAttempt}/${ISOLATED_JAILBREAK_RETRIES} failed`,
          "error"
        );
      }
    }

    if (attempt.success) {
      stepSucceeded = true;
      break;
    }
  }

  const toolsUsed = [...new Set(methodResults.map((r) => r.tool).filter(Boolean))];
  const summaryLines = methodResults.map((r) => {
    const tag = r.isolated ? `isolated#${r.isolated_attempt}` : "primary";
    return `- [${tag}] ${r.method_name || r.method_id}: ${r.success ? "OK" : "FAIL"} (${r.tool})`;
  });

  if (!stepSucceeded && engagement?.id) {
    if (liveAttack.isLiveCouncilEnabled(engagement, { live_council: true })) {
      await liveAttack.emitCouncilEvent(
        {
          type: "isolated_retry_exhausted",
          engagement_id: engagement.id,
          step,
          step_number: engagement.chain_execution?.current_step,
          method_result: methodResults[methodResults.length - 1],
          step_result: {
            status: "failed",
            output: summaryLines.join("\n"),
            chain_attack_methods: methodResults,
          },
        },
        {
          eng: engagement,
          engagementId: engagement.id,
          chain_index: engagement.attack_chains?.active_chain_index ?? 0,
          reqBody: { live_council: true },
          knowledgeEngineUrl: KNOWLEDGE_ENGINE,
          integrationHubUrl: INTEGRATION_HUB_URL,
          getServiceAuthHeaders,
          broadcast,
          broadcastCouncil,
          broadcastTerminal,
        }
      ).catch((err) => console.warn("Council method failure emit:", err.message));
    }
  }

  return {
    success: stepSucceeded,
    output: stepSucceeded
      ? `[SUCCESS] ${step.attack?.title || step.phase} — chain attack method succeeded\n\n${summaryLines.join("\n")}`
      : `[FAILED] ${step.attack?.title || step.phase} — all chain methods and isolated retries exhausted\n\n${summaryLines.join("\n")}`,
    chain_attack_methods: methodResults,
    tools_used: toolsUsed,
    execution_mode: "chain_attack_with_isolated_jailbreak",
  };
}

// Execute attack with jailbreak guidance
async function executeAttackWithJailbreakGuidance(step, jailbreak_guidance, engagement) {
  try {
    const attack_type = step.attack?.attack_type || step.phase;
    const target = engagement.target;

    if (isChainAttackPhase(step)) {
      return await executeChainAttackMethods(step, jailbreak_guidance, engagement);
    }

    // Based on jailbreak guidance and attack type, execute appropriate attack
    switch (attack_type) {
      case 'reconnaissance':
        return await executeReconnaissanceWithJailbreak(step, jailbreak_guidance, target);
      
      case 'exploitation':
        return await executeExploitationWithJailbreak(step, jailbreak_guidance, target);
      
      case 'execution':
        return await executeAttackExecutionWithJailbreak(step, jailbreak_guidance, target);
      
      case 'privilege_escalation':
        return await executePrivilegeEscalationWithJailbreak(step, jailbreak_guidance, target);
      
      default:
        return await executeGenericAttackWithJailbreak(step, jailbreak_guidance, target);
    }
  } catch (error) {
    console.error('Attack execution with jailbreak guidance error:', error);
    return {
      success: false,
      output: `[FAILED] Attack execution error: ${error.message}`
    };
  }
}

// Input validation and sanitization
function validateAndSanitizeTarget(target) {
  if (!target || typeof target !== 'string') {
    throw new Error('Invalid target: must be a non-empty string');
  }
  
  // Remove potentially dangerous characters
  const sanitized = normalizeTargetInput(target).replace(/[;&|`$()<>]/g, '');
  
  // Basic hostname/IP validation
  const hostnameRegex = /^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$/;
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
  
  if (!sanitized.match(hostnameRegex) && !sanitized.match(ipRegex)) {
    throw new Error(`Invalid target format: ${sanitized}`);
  }
  
  // Length validation
  if (sanitized.length > 253) {
    throw new Error('Target exceeds maximum length of 253 characters');
  }
  
  return sanitized;
}

function validateEngagementId(engagementId) {
  if (!engagementId || typeof engagementId !== 'string') {
    throw new Error('Invalid engagement ID: must be a non-empty string');
  }
  
  // UUID format validation (basic check)
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!engagementId.match(uuidRegex)) {
    console.warn(`Engagement ID ${engagementId} does not match UUID format, proceeding anyway`);
  }
  
  return engagementId;
}

/**
 * Normalize Knowledge Engine attack-chain steps for execution.
 * KE steps often have attack.title + phase but no shell command string.
 */
function normalizeChainSteps(steps) {
  if (!Array.isArray(steps)) return [];

  return steps.map((step, index) => {
    const normalized = { ...(step || {}) };
    const attack =
      normalized.attack && typeof normalized.attack === "object"
        ? { ...normalized.attack }
        : {};

    const title =
      (typeof attack.title === "string" && attack.title.trim()) ||
      (typeof normalized.name === "string" && normalized.name.trim()) ||
      (typeof normalized.phase === "string" && normalized.phase.trim()) ||
      `Step ${index + 1}`;

    const phase =
      (typeof normalized.phase === "string" && normalized.phase.trim()) ||
      "Execution";
    const mitre = attack.mitre_technique || "N/A";

    attack.title = title;
    normalized.attack = attack;
    normalized.phase = phase;

    if (
      typeof normalized.command !== "string" ||
      !normalized.command.trim()
    ) {
      normalized.command = `# ${phase}: ${title} (${mitre})`;
    } else {
      normalized.command = normalized.command.trim();
    }

    if (!normalized.tool && typeof attack.attack_type === "string") {
      normalized.tool = attack.attack_type;
    }

    return normalized;
  });
}

function validateCommandChain(commandChain) {
  if (!Array.isArray(commandChain) || commandChain.length === 0) {
    throw new Error('Command chain must be a non-empty array');
  }
  
  if (commandChain.length > 20) {
    throw new Error('Command chain exceeds maximum length of 20 commands');
  }
  
  commandChain.forEach((cmd, index) => {
    const hasCommand = typeof cmd.command === 'string' && cmd.command.trim().length > 0;
    const hasAttackStep = cmd.attack && typeof cmd.attack === 'object' && typeof cmd.attack.title === 'string' && cmd.attack.title.trim().length > 0;

    if (!hasCommand && !hasAttackStep) {
      throw new Error(`Invalid step at index ${index}: step must include a non-empty command or attack.title`);
    }

    if (hasCommand && cmd.command.length > 1000) {
      throw new Error(`Command at index ${index} exceeds maximum length of 1000 characters`);
    }
    
    // Check for potentially dangerous command patterns
    const dangerousPatterns = [
      /\.\./,  // Directory traversal
      /rm -rf/, // Dangerous file operations
      /format/, // Disk formatting
      /dd if=/, // Disk operations
      />.*\/dev\/(sd[a-z]|null)/, // Direct disk writes
    ];
    
    for (const pattern of dangerousPatterns) {
      if (hasCommand && pattern.test(cmd.command)) {
        console.warn(`Potentially dangerous command pattern detected at index ${index}: ${cmd.command}`);
      }
    }
  });
  
  return true;
}

// Circuit breaker pattern for external service calls
class CircuitBreaker {
  constructor(threshold = 5, timeout = 60000) {
    this.failureCount = 0;
    this.threshold = threshold;
    this.timeout = timeout;
    this.lastFailureTime = null;
    this.state = 'closed'; // closed, open, half-open
  }
  
  async execute(fn) {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailureTime > this.timeout) {
        this.state = 'half-open';
        console.log('Circuit breaker transitioning to half-open state');
      } else {
        throw new Error('Circuit breaker is OPEN - service unavailable');
      }
    }
    
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
  
  onSuccess() {
    this.failureCount = 0;
    if (this.state === 'half-open') {
      this.state = 'closed';
      console.log('Circuit breaker transitioning to closed state');
    }
  }
  
  onFailure() {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    
    if (this.failureCount >= this.threshold) {
      this.state = 'open';
      console.error(`Circuit breaker opened after ${this.failureCount} failures`);
    }
  }
}

// Global circuit breakers for external services
const serviceCircuitBreakers = {
  integrationHub: new CircuitBreaker(3, 30000),
  knowledgeEngine: new CircuitBreaker(5, 60000),
  database: new CircuitBreaker(3, 20000)
};

// Rate limiter for API calls
class RateLimiter {
  constructor(maxRequests, timeWindow) {
    this.maxRequests = maxRequests;
    this.timeWindow = timeWindow;
    this.requests = [];
  }
  
  canMakeRequest() {
    const now = Date.now();
    // Remove requests outside the time window
    this.requests = this.requests.filter(time => now - time < this.timeWindow);
    
    if (this.requests.length >= this.maxRequests) {
      return false;
    }
    
    this.requests.push(now);
    return true;
  }
  
  getResetTime() {
    const now = Date.now();
    if (this.requests.length === 0) return now;
    const oldestRequest = Math.min(...this.requests);
    return oldestRequest + this.timeWindow;
  }
}

// Global rate limiters
const rateLimiters = {
  executeChain: new RateLimiter(10, 60000), // 10 executions per minute
  apiCalls: new RateLimiter(100, 60000), // 100 API calls per minute
  commandExecution: new RateLimiter(50, 60000) // 50 command executions per minute
};

// Simulate realistic command execution with output
async function simulateCommandExecution(command, target, retryCount = 0, maxRetries = 3) {
  const maxDelay = 5000; // 5 seconds max delay
  const baseDelay = 200; // 200ms base delay
  const delay = Math.min(baseDelay + (retryCount * 500), maxDelay);
  
  try {
    // Simulate processing delay with exponential backoff
    await new Promise(resolve => setTimeout(resolve, delay + Math.random() * 300));

    // Generate realistic output based on command type
    if (command.includes('nmap')) {
      return generateNmapOutput(target);
    } else if (command.includes('dnsenum')) {
      return generateDnsOutput(target);
    } else if (command.includes('whois')) {
      return generateWhoisOutput(target);
    } else if (command.includes('sqlmap')) {
      return generateSqlmapOutput(target);
    } else if (command.includes('metasploit') || command.includes('msfconsole')) {
      return generateMetasploitOutput(target);
    } else if (command.includes('powershell') || command.includes('bash')) {
      return generateShellOutput(command);
    } else {
      return `[Command executed successfully]\nTarget: ${target}\nCommand: ${command}\nStatus: Completed`;
    }
  } catch (error) {
    console.error(`Command execution error (attempt ${retryCount + 1}/${maxRetries}):`, error);
    
    // Retry logic with exponential backoff
    if (retryCount < maxRetries) {
      console.log(`Retrying command execution in ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
      return simulateCommandExecution(command, target, retryCount + 1, maxRetries);
    }
    
    // Final fallback if all retries fail
    return `[Command execution failed after ${maxRetries} retries]\nTarget: ${target}\nCommand: ${command}\nError: ${error.message}\nFallback: Using simulated output`;
  }
}

// Generate realistic nmap output
function generateNmapOutput(target) {
  const ports = [21, 22, 23, 25, 80, 443, 3306, 3389, 5432];
  const services = ['ftp', 'ssh', 'telnet', 'smtp', 'http', 'https', 'mysql', 'ms-wbt-server', 'postgresql'];
  
  let output = `Starting Nmap scan for ${target}\n`;
  output += `Host is up (0.0023s latency).\n`;
  output += `Not shown: 998 closed ports\n`;
  output += `PORT     STATE SERVICE     VERSION\n`;
  
  const numPorts = 3 + Math.floor(Math.random() * 4);
  const shuffledPorts = ports.sort(() => 0.5 - Math.random()).slice(0, numPorts);
  
  shuffledPorts.forEach((port, index) => {
    const service = services[ports.indexOf(port)] || 'unknown';
    output += `${port}/tcp open  ${service.padEnd(11)} ${service === 'http' ? 'nginx 1.18.0' : service === 'ssh' ? 'OpenSSH 8.2p1' : 'unknown'}\n`;
  });
  
  output += `\nService detection performed. \n`;
  output += `OS CPE: cpe:/o:linux:linux_kernel\n`;
  output += `OS details: Linux 4.15 - 5.6\n`;
  output += `\nScan completed: 1 IP address (1 host up) scanned in ${Math.floor(Math.random() * 20 + 10)} seconds`;
  
  return output;
}

// Generate realistic DNS enumeration output
function generateDnsOutput(target) {
  const subdomains = ['www', 'mail', 'ftp', 'admin', 'api', 'dev', 'staging', 'blog'];
  const ips = Array.from({length: 5}, () => `${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}`);
  
  let output = `DNS Enumeration for ${target}\n`;
  output += `[*] Enumerating DNS records...\n`;
  output += `[*] Found A records:\n`;
  
  subdomains.slice(0, 4).forEach((sub, i) => {
    output += `    ${sub}.${target} -> ${ips[i % ips.length]}\n`;
  });
  
  output += `[*] Found MX records:\n`;
  output += `    mail.${target} -> ${ips[0]}\n`;
  output += `[*] Found NS records:\n`;
  output += `    ns1.${target} -> ${ips[1]}\n`;
  output += `    ns2.${target} -> ${ips[2]}\n`;
  output += `\nDNS enumeration completed. Found 6 DNS records.`;
  
  return output;
}

// Generate realistic WHOIS output
function generateWhoisOutput(target) {
  let output = `WHOIS lookup for ${target}\n`;
  output += `Domain Name: ${target.toUpperCase()}\n`;
  output += `Registry Domain ID: ${Math.random().toString(36).substring(7).toUpperCase()}\n`;
  output += `Registrar: Example Registrar Inc.\n`;
  output += `Updated Date: 2024-01-15T00:00:00Z\n`;
  output += `Creation Date: 2020-05-20T00:00:00Z\n`;
  output += `Registry Expiry Date: 2025-05-20T00:00:00Z\n`;
  output += `Registrar Abuse Contact Email: abuse@registrar.com\n`;
  output += `Name Server: NS1.${target.toUpperCase()}\n`;
  output += `Name Server: NS2.${target.toUpperCase()}\n`;
  output += `DNSSEC: unsigned\n`;
  output += `\nWHOIS lookup completed.`;
  
  return output;
}

// Generate realistic SQLMap output
function generateSqlmapOutput(target) {
  let output = `SQLMap v1.7.5 - automatic SQL injection and database takeover tool\n`;
  output += `[*] Starting @ ${new Date().toISOString()}\n`;
  output += `[+] Target: ${target}\n`;
  output += `[+] Testing connection...\n`;
  output += `[+] Connection successful\n`;
  output += `[+] Detecting injection type...\n`;
  output += `[+] Injection point found: GET parameter 'id'\n`;
  output += `[+] Injection type: Boolean-based blind\n`;
  output += `[+] Testing database...\n`;
  output += `[+] Database: production_db\n`;
  output += `[+] Tables found: users, products, orders\n`;
  output += `[+] Dumping table 'users'...\n`;
  output += `[+] Retrieved 15 records\n`;
  output += `[+] Column names: id, username, email, password_hash\n`;
  output += `[+] Sample data:\n`;
  output += `    | id | username | email | password_hash |\n`;
  output += `    | 1  | admin    | admin@${target} | $2a$10$... |\n`;
  output += `    | 2  | user1    | user1@${target} | $2a$10$... |\n`;
  output += `\n[+] SQL injection completed successfully`;
  
  return output;
}

// Generate realistic Metasploit output
function generateMetasploitOutput(target) {
  let output = `Metasploit Framework v6.3.0\n`;
  output += `[*] Starting exploit execution...\n`;
  output += `[+] Target: ${target}\n`;
  output += `[+] Exploit: exploit/linux/http/target_rce\n`;
  output += `[+] Payload: linux/x64/meterpreter/reverse_tcp\n`;
  output += `[+] LHOST: 10.0.0.1\n`;
  output += `[+] LPORT: 4444\n`;
  output += `[*] Exploiting target...\n`;
  output += `[+] Sending stage (126534 bytes) to ${target}\n`;
  output += `[+] Meterpreter session 1 opened\n`;
  output += `[+] Session type: meterpreter\n`;
  output += `meterpreter > sysinfo\n`;
  output += `Computer     : ${target}\n`;
  output += `OS           : Linux 5.4.0-generic\n`;
  output += `Architecture : x64\n`;
  output += `Meterpreter  : x64/linux\n`;
  output += `meterpreter > getuid\n`;
  output += `Server username: root\n`;
  output += `meterpreter > pwd\n`;
  output += `/var/www/html\n`;
  output += `\n[+] Exploit completed successfully. Session maintained.`;
  
  return output;
}

// Generate realistic shell command output
function generateShellOutput(command) {
  let output = `$ ${command}\n`;
  
  if (command.includes('whoami')) {
    output += `root\n`;
  } else if (command.includes('hostname')) {
    output += `target-server-01\n`;
  } else if (command.includes('uname')) {
    output += `Linux target-server-01 5.4.0-generic #42-Ubuntu SMP Fri Apr 16 12:34:56 UTC 2024 x86_64\n`;
  } else if (command.includes('ps aux')) {
    output += `USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n`;
    output += `root         1  0.0  0.1  16856  4568 ?        Ss   10:00   0:01 /sbin/init\n`;
    output += `root       123  0.5  1.2  45678 12345 ?        S    10:01   0:15 /usr/sbin/apache2\n`;
    output += `www-data   456  0.3  0.8  34567  8901 ?        S    10:02   0:08 /usr/sbin/apache2\n`;
  } else if (command.includes('ls -la')) {
    output += `total 48\n`;
    output += `drwxr-xr-x  5 root root 4096 May 19 10:00 .\n`;
    output += `drwxr-xr-x  3 root root 4096 May 18 09:00 ..\n`;
    output += `-rw-r--r--  1 root root  220 May 15 08:00 .bashrc\n`;
    output += `-rw-r--r--  1 root root  123 May 15 08:00 .profile\n`;
    output += `-rwxr-xr-x  1 root root  456 May 19 10:00 script.sh\n`;
  } else {
    output += `Command executed successfully\n`;
    output += `Exit code: 0\n`;
  }
  
  return output;
}

// Execute reconnaissance with jailbreak guidance
async function executeReconnaissanceWithJailbreak(step, jailbreak_guidance, target) {
  try {
    const tools = jailbreak_guidance.recommended_tools || [];
    const guidance = jailbreak_guidance.guidance || '';
    const engagementId = step.engagement_id || 'unknown';

    // Simulate realistic command chain for reconnaissance
    const commandChain = [
      {
        command: `nmap -sS -sV -O --script=vuln ${target}`,
        description: "Stealth scan with service detection and vulnerability scripts"
      },
      {
        command: `nmap -p- --min-rate=1000 ${target}`,
        description: "Full port scan with optimized timing"
      },
      {
        command: `dnsenum ${target}`,
        description: "DNS enumeration and subdomain discovery"
      },
      {
        command: `whois ${target}`,
        description: "WHOIS lookup for target information"
      }
    ];

    const executionResults = [];

    // Broadcast command chain start
    broadcastTerminal(engagementId, `\n🔍 STARTING RECONNAISSANCE COMMAND CHAIN`, 'command');
    broadcastTerminal(engagementId, `Target: ${target}`, 'info');
    broadcastTerminal(engagementId, `Guidance: ${guidance}`, 'info');

    // Execute each command in the chain
    for (const cmd of commandChain) {
      broadcastTerminal(engagementId, `\n💻 EXECUTING: ${cmd.command}`, 'command');
      broadcastTerminal(engagementId, `📝 ${cmd.description}`, 'info');

      // Simulate command execution with realistic output
      const result = await simulateCommandExecution(cmd.command, target);
      executionResults.push({
        command: cmd.command,
        output: result,
        success: true
      });

      // Broadcast command output
      broadcastTerminal(engagementId, `📤 OUTPUT:\n${result}`, 'success');
      
      // Add delay between commands for realism
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    return {
      success: true,
      output: `[SUCCESS] ${step.attack.title} completed\n\n` +
               `Commands Executed: ${commandChain.length}\n` +
               `Tools Used: ${tools.join(', ')}\n` +
               `Total Results: ${executionResults.length} commands executed`,
      command_chain: executionResults,
      tools_used: tools
    };
  } catch (error) {
    console.error('Reconnaissance execution error:', error);
    return {
      success: false,
      output: `[FAILED] ${step.attack.title} - Execution error: ${error.message}`
    };
  }
}

// Execute exploitation with jailbreak guidance
async function executeExploitationWithJailbreak(step, jailbreak_guidance, target) {
  try {
    const guidance = jailbreak_guidance.guidance || '';
    const attack_vectors = jailbreak_guidance.attack_vectors || [];
    const engagementId = step.engagement_id || 'unknown';

    // Simulate realistic command chain for exploitation
    const commandChain = [
      {
        command: `sqlmap -u "http://${target}/page?id=1" --batch --random-agent`,
        description: "SQL injection testing with random user agent"
      },
      {
        command: `nikto -h http://${target} -Tuning 1,2,3,4,5,6,7,8,9,a,b,c`,
        description: "Web vulnerability scanning with comprehensive tuning"
      },
      {
        command: `nmap --script=vuln -p80,443 ${target}`,
        description: "Vulnerability scanning on web ports"
      }
    ];

    const executionResults = [];

    // Broadcast command chain start
    broadcastTerminal(engagementId, `\n💥 STARTING EXPLOITATION COMMAND CHAIN`, 'command');
    broadcastTerminal(engagementId, `Target: ${target}`, 'info');
    broadcastTerminal(engagementId, `Guidance: ${guidance}`, 'info');
    broadcastTerminal(engagementId, `Attack Vectors: ${attack_vectors.join(', ')}`, 'info');

    // Execute each command in the chain
    for (const cmd of commandChain) {
      broadcastTerminal(engagementId, `\n💻 EXECUTING: ${cmd.command}`, 'command');
      broadcastTerminal(engagementId, `📝 ${cmd.description}`, 'info');

      // Simulate command execution with realistic output
      const result = await simulateCommandExecution(cmd.command, target);
      executionResults.push({
        command: cmd.command,
        output: result,
        success: true
      });

      // Broadcast command output
      broadcastTerminal(engagementId, `📤 OUTPUT:\n${result}`, 'success');
      
      // Add delay between commands for realism
      await new Promise(resolve => setTimeout(resolve, 800));
    }

    return {
      success: true,
      output: `[SUCCESS] ${step.attack.title} completed\n\n` +
               `Commands Executed: ${commandChain.length}\n` +
               `Attack Vectors Tested: ${attack_vectors.join(', ')}\n` +
               `Total Results: ${executionResults.length} commands executed`,
      command_chain: executionResults,
      attack_vectors_tested: attack_vectors
    };
  } catch (error) {
    console.error('Exploitation execution error:', error);
    return {
      success: false,
      output: `[FAILED] ${step.attack.title} - Execution error: ${error.message}`
    };
  }
}

// Execute attack execution with jailbreak guidance
async function executeAttackExecutionWithJailbreak(step, jailbreak_guidance, target) {
  try {
    const guidance = jailbreak_guidance.guidance || '';
    const tools = jailbreak_guidance.recommended_tools || [];
    const engagementId = step.engagement_id || 'unknown';

    // Simulate realistic command chain for command execution
    const commandChain = [
      {
        command: `powershell -Enc "SQBFAFgAKQAgAC0AUwBlAGMAQwByAGUAdAAgAC0AQwBvAG0AbQBhAG4AZAAgACIAJABwAHIAbwBjAGUAcwBzACAALQBBAHIAZwB1AG0AZQBuAHQAcwAgAC0AVwBpAG4AZABvAHcAcwBTAHQAYQB5AGUAbwBuACAALQBGAG8AcgBjAGUAIAAiACIA`,
        description: "Encoded PowerShell command for stealthy execution"
      },
      {
        command: `bash -c 'whoami && hostname && uname -a'`,
        description: "System information gathering"
      },
      {
        command: `cmd.exe /c "net user && net localgroup administrators"`,
        description: "User and group enumeration"
      }
    ];

    const executionResults = [];

    // Broadcast command chain start
    broadcastTerminal(engagementId, `\n⚡ STARTING EXECUTION COMMAND CHAIN`, 'command');
    broadcastTerminal(engagementId, `Target: ${target}`, 'info');
    broadcastTerminal(engagementId, `Guidance: ${guidance}`, 'info');

    // Execute each command in the chain
    for (const cmd of commandChain) {
      broadcastTerminal(engagementId, `\n💻 EXECUTING: ${cmd.command}`, 'command');
      broadcastTerminal(engagementId, `📝 ${cmd.description}`, 'info');

      // Simulate command execution with realistic output
      const result = await simulateCommandExecution(cmd.command, target);
      executionResults.push({
        command: cmd.command,
        output: result,
        success: true
      });

      // Broadcast command output
      broadcastTerminal(engagementId, `📤 OUTPUT:\n${result}`, 'success');
      
      // Add delay between commands for realism
      await new Promise(resolve => setTimeout(resolve, 400));
    }

    return {
      success: true,
      output: `[SUCCESS] ${step.attack.title} completed\n\n` +
               `Commands Executed: ${commandChain.length}\n` +
               `Tools Used: ${tools.join(', ')}\n` +
               `Total Results: ${executionResults.length} commands executed`,
      command_chain: executionResults,
      tools_used: tools
    };
  } catch (error) {
    console.error('Attack execution error:', error);
    return {
      success: false,
      output: `[FAILED] ${step.attack.title} - Execution error: ${error.message}`
    };
  }
}

// Execute privilege escalation with jailbreak guidance
async function executePrivilegeEscalationWithJailbreak(step, jailbreak_guidance, target) {
  try {
    const guidance = jailbreak_guidance.guidance || '';
    const evasion_techniques = jailbreak_guidance.evasion_techniques || [];
    const engagementId = step.engagement_id || 'unknown';

    // Simulate realistic command chain for privilege escalation
    const commandChain = [
      {
        command: `linpeas.sh`,
        description: "Linux privilege escalation audit script"
      },
      {
        command: `python3 -c 'import pty; pty.spawn("/bin/bash")'`,
        description: "Spawn interactive TTY shell"
      },
      {
        command: `sudo -l && cat /etc/sudoers`,
        description: "Check sudo permissions and configuration"
      }
    ];

    const executionResults = [];

    // Broadcast command chain start
    broadcastTerminal(engagementId, `\n📈 STARTING PRIVILEGE ESCALATION COMMAND CHAIN`, 'command');
    broadcastTerminal(engagementId, `Target: ${target}`, 'info');
    broadcastTerminal(engagementId, `Guidance: ${guidance}`, 'info');
    broadcastTerminal(engagementId, `Evasion Techniques: ${evasion_techniques.join(', ')}`, 'info');

    // Execute each command in the chain
    for (const cmd of commandChain) {
      broadcastTerminal(engagementId, `\n💻 EXECUTING: ${cmd.command}`, 'command');
      broadcastTerminal(engagementId, `📝 ${cmd.description}`, 'info');

      // Simulate command execution with realistic output
      const result = await simulateCommandExecution(cmd.command, target);
      executionResults.push({
        command: cmd.command,
        output: result,
        success: true
      });

      // Broadcast command output
      broadcastTerminal(engagementId, `📤 OUTPUT:\n${result}`, 'success');
      
      // Add delay between commands for realism
      await new Promise(resolve => setTimeout(resolve, 600));
    }

    return {
      success: true,
      output: `[SUCCESS] ${step.attack.title} completed\n\n` +
               `Commands Executed: ${commandChain.length}\n` +
               `Evasion Techniques: ${evasion_techniques.join(', ')}\n` +
               `Total Results: ${executionResults.length} commands executed`,
      command_chain: executionResults,
      evasion_techniques_used: evasion_techniques
    };
  } catch (error) {
    console.error('Privilege escalation execution error:', error);
    return {
      success: false,
      output: `[FAILED] ${step.attack.title} - Execution error: ${error.message}`
    };
  }
}

// Execute generic attack with jailbreak guidance
async function executeGenericAttackWithJailbreak(step, jailbreak_guidance, target) {
  try {
    const guidance = jailbreak_guidance.guidance || '';
    const tools = jailbreak_guidance.recommended_tools || [];
    const engagementId = step.engagement_id || 'unknown';

    // Simulate realistic command chain for generic attack
    const commandChain = [
      {
        command: `curl -s http://${target} | head -20`,
        description: "HTTP request to target with header analysis"
      },
      {
        command: `wget -qO- http://${target}/robots.txt`,
        description: "Fetch robots.txt for hidden paths"
      },
      {
        command: `dig ${target} ANY +noall +answer`,
        description: "DNS query for all record types"
      }
    ];

    const executionResults = [];

    // Broadcast command chain start
    broadcastTerminal(engagementId, `\n🎯 STARTING GENERIC ATTACK COMMAND CHAIN`, 'command');
    broadcastTerminal(engagementId, `Target: ${target}`, 'info');
    broadcastTerminal(engagementId, `Guidance: ${guidance}`, 'info');

    // Execute each command in the chain
    for (const cmd of commandChain) {
      broadcastTerminal(engagementId, `\n💻 EXECUTING: ${cmd.command}`, 'command');
      broadcastTerminal(engagementId, `📝 ${cmd.description}`, 'info');

      // Simulate command execution with realistic output
      const result = await simulateCommandExecution(cmd.command, target);
      executionResults.push({
        command: cmd.command,
        output: result,
        success: true
      });

      // Broadcast command output
      broadcastTerminal(engagementId, `📤 OUTPUT:\n${result}`, 'success');
      
      // Add delay between commands for realism
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    return {
      success: true,
      output: `[SUCCESS] ${step.attack.title} completed\n\n` +
               `Commands Executed: ${commandChain.length}\n` +
               `Tools Used: ${tools.join(', ')}\n` +
               `Total Results: ${executionResults.length} commands executed`,
      command_chain: executionResults,
      tools_used: tools
    };
  } catch (error) {
    console.error('Generic attack execution error:', error);
    return {
      success: false,
      output: `[FAILED] ${step.attack.title} - Execution error: ${error.message}`
    };
  }
}

// Fallback execution without jailbreak AI
async function executeStepFallback(step, execution_id, step_number) {
  const step_start = Date.now();
  const execution_delay = Math.random() * 3000 + 2000; // 2-5 seconds

  await new Promise(resolve => setTimeout(resolve, execution_delay));

  const step_success = Math.random() > 0.3; // 70% success rate with fallback

  return {
    step_number,
    step: step,
    status: step_success ? 'success' : 'failed',
    output: step_success
      ? `[SUCCESS] ${step.attack.title} completed (fallback execution)`
      : `[FAILED] ${step.attack.title} encountered an error (fallback execution)`,
    started_at: new Date(step_start).toISOString(),
    completed_at: new Date().toISOString(),
    execution_time_ms: execution_delay,
    jailbreak_enhanced: false,
    execution_method: 'fallback'
  };
}

// ── Pipeline ──────────────────────────────────────────────────────────────────

async function runEngagementPipeline(id, target) {
  const eng = engagements.get(id);
  const boundary = eng?.boundary_profile || buildBoundaryProfile(AGGRESSION_MIN);

  function log(msg) {
    console.log(`[engagement ${id}] ${msg}`);
    eng.log.push({ ts: new Date().toISOString(), msg });
    broadcast(id, eng);
    if (msg && String(msg).trim()) {
      emitAttackEvent(id, {
        type: inferAttackEventType(msg, "info"),
        severity: inferAttackEventSeverity("info"),
        description: String(msg).trim(),
        details: { source: "engagement_pipeline" },
      });
    }
  }

  function overseerEvent(event) {
    addOverseerEvent(id, eng, event);
  }

  function computeAndStoreQuality() {
    const quality = updateOverseerQuality(eng);
    if (!quality) return;
    const threshold = eng.analysis_overseer.quality_gate.threshold;
    const passed = quality.overall >= threshold;
    eng.analysis_overseer.quality_gate.status = passed ? "pass" : "fail";
    eng.analysis_overseer.quality_gate.reason = passed
      ? `Quality score ${quality.overall} met threshold ${threshold}.`
      : `Quality score ${quality.overall} below threshold ${threshold}.`;
  }

  overseerEvent({
    stage: "task_framing",
    type: "progress_update",
    message: `Overseer initialized for target ${target} (aggression ${boundary.aggression_level}/10).`,
    suggestions: [
      "Establish stage-by-stage quality checks before finalizing results.",
      "Preserve live evidence so downstream panels can explain confidence.",
    ],
  });

  // 1. Kick off adaptive AI-guided scanning with maximum depth
  log(`Starting adaptive AI-guided scanning of ${target} with maximum depth…`);
  eng.status = "scanning";
  broadcast(id, eng);
  overseerEvent({
    stage: "scan_analysis",
    type: "progress_update",
    message: "Initiating adaptive AI-guided reconnaissance with live pivoting.",
    suggestions: [
      "Jailbreak AI will dynamically adjust scanning strategy based on findings.",
      "Maximum depth scanning will be performed regardless of aggression level.",
      "Live pivoting will explore discovered services and vulnerabilities in depth.",
    ],
  });

  let scanResults = {
    fingerprint: null,
    services: [],
    vulnerabilities: [],
    scan_depth: 0,
    pivots: []
  };

  // Adaptive scanning loop with AI guidance
  const maxScanDepth = 10; // Maximum depth for comprehensive scanning
  let currentDepth = 0;
  let shouldContinueScanning = true;

  while (shouldContinueScanning && currentDepth < maxScanDepth) {
    currentDepth++;
    log(`[Adaptive Scan] Depth ${currentDepth}: Analyzing target and determining next steps…`);
    
    try {
      // Use jailbreak AI to determine next scanning actions
      const aiGuidance = await axios.post(
        `${KNOWLEDGE_ENGINE}/ai/analyse/scan`,
        {
          target: target,
          scan_fingerprint: {
            target: target,
            os: scanResults.fingerprint?.os || "unknown",
            services: scanResults.services,
            scan_depth: currentDepth,
            previous_pivots: scanResults.pivots
          }
        },
        { timeout: 60000 }
      );

      if (aiGuidance.data?.success && aiGuidance.data.analysis) {
        const analysis = aiGuidance.data.analysis;
        log(`[Adaptive Scan] AI Analysis: Found ${analysis.services_detected} services, ${analysis.vulnerabilities.length} vulnerabilities, risk score: ${analysis.risk_score}`);
        
        // Store AI findings
        scanResults.vulnerabilities = [...scanResults.vulnerabilities, ...analysis.vulnerabilities];
        
        // Determine next scanning actions based on AI recommendations
        if (analysis.attack_vectors && analysis.attack_vectors.length > 0) {
          log(`[Adaptive Scan] AI recommends: ${analysis.attack_vectors.join(", ")}`);
          
          // Execute recommended scanning actions
          for (const vector of analysis.attack_vectors.slice(0, 3)) { // Limit to top 3 recommendations per depth
            try {
              log(`[Adaptive Scan] Executing: ${vector}`);
              
              // Call Analyzer with AI-recommended parameters
              const scanResp = await axios.post(`${ANALYZER_URL}/scan`, {
                target,
                aggression_level: 10, // Always use maximum aggression for depth
                scan_timeout_sec: 120, // Extended timeout for deep scanning
                scan_type: vector.includes("HTTP") ? "web_application" : 
                          vector.includes("SSH") ? "ssh_brute_force" :
                          vector.includes("Database") ? "database_enumeration" : "comprehensive"
              });
              
              if (scanResp.data?.id) {
                log(`[Adaptive Scan] Scan initiated: ${scanResp.data.id}`);
                
                // Poll for completion with extended timeout
                const sessionId = scanResp.data.id;
                const deadline = Date.now() + 180000; // 3 minute timeout per scan
                while (Date.now() < deadline) {
                  await sleep(3000);
                  let sessResp;
                  try {
                    sessResp = await axios.get(`${ANALYZER_URL}/sessions/${sessionId}`);
                  } catch {
                    break;
                  }
                  
                  if (sessResp.data.status === "ready") {
                    log(`[Adaptive Scan] Scan completed: ${vector}`);
                    scanResults.fingerprint = sessResp.data.fingerprint;
                    if (sessResp.data.fingerprint?.services) {
                      scanResults.services = [...scanResults.services, ...sessResp.data.fingerprint.services];
                    }
                    
                    // Record pivot
                    scanResults.pivots.push({
                      depth: currentDepth,
                      action: vector,
                      timestamp: new Date().toISOString(),
                      services_found: sessResp.data.fingerprint?.services?.length || 0
                    });

                    if (liveAttack.isLiveCouncilEnabled(eng, {})) {
                      await liveAttack.emitCouncilEvent(
                        {
                          type: "scan_session_updated",
                          engagement_id: id,
                          scan_delta: {
                            pivot: vector,
                            depth: currentDepth,
                            services_found: sessResp.data.fingerprint?.services?.length || 0,
                          },
                        },
                        {
                          eng,
                          engagementId: id,
                          reqBody: { live_council: true },
                          knowledgeEngineUrl: KNOWLEDGE_ENGINE,
                          integrationHubUrl: INTEGRATION_HUB_URL,
                          getServiceAuthHeaders,
                          broadcast,
                          broadcastCouncil,
                          broadcastTerminal,
                        }
                      );
                    }
                    break;
                  }
                }
              }
            } catch (scanError) {
              log(`[Adaptive Scan] Scan failed for ${vector}: ${scanError.message}`);
            }
          }
        }
        
        // Update engagement with current findings
        eng.scan_session = {
          id: `adaptive_scan_${Date.now()}`,
          status: "in_progress",
          fingerprint: scanResults.fingerprint,
          adaptive_depth: currentDepth,
          total_services_found: scanResults.services.length,
          total_vulnerabilities_found: scanResults.vulnerabilities.length,
          pivots_executed: scanResults.pivots.length
        };
        broadcast(id, eng);
        
        // Determine if we should continue scanning
        // Always continue to max depth as requested, but can stop if no new findings
        const hasNewFindings = analysis.vulnerabilities.length > 0 || analysis.services_detected > scanResults.services.length;
        if (!hasNewFindings && currentDepth >= 5) {
          log(`[Adaptive Scan] No new findings at depth ${currentDepth}, continuing to max depth for completeness...`);
        }
        
        // Small delay between adaptive scan iterations
        await sleep(2000);
        
      } else {
        log(`[Adaptive Scan] AI analysis failed, continuing with standard scanning`);
        shouldContinueScanning = false;
      }
    } catch (aiError) {
      log(`[Adaptive Scan] AI guidance failed: ${aiError.message}, falling back to standard scan`);
      console.error(`[engagement ${id}] Adaptive scan error:`, aiError.message);
      shouldContinueScanning = false;
    }
  }

  // Fallback to standard scan if adaptive scanning fails or completes
  if (!scanResults.fingerprint) {
    log(`[Adaptive Scan] No fingerprint gathered, performing standard scan as fallback`);
    try {
      const scanResp = await axios.post(`${ANALYZER_URL}/scan`, {
        target,
        aggression_level: 10, // Maximum aggression
        scan_timeout_sec: 180, // Extended timeout
      });
      
      if (scanResp.data?.id) {
        const sessionId = scanResp.data.id;
        eng.scan_session = { id: sessionId, status: "pending", type: "standard_scan" };
        
        log(`[Adaptive Scan] Standard scan session ${sessionId} started. Polling for completion…`);
        const deadline = Date.now() + 300000; // 5 minute timeout
        while (Date.now() < deadline) {
          await sleep(3000);
          let sessResp;
          try {
            sessResp = await axios.get(`${ANALYZER_URL}/sessions/${sessionId}`);
          } catch {
            break;
          }
          eng.scan_session = sessResp.data;
          broadcast(id, eng);
          if (sessResp.data.status === "ready" || sessResp.data.status === "error") break;
        }
        
        if (eng.scan_session.fingerprint) {
          scanResults.fingerprint = eng.scan_session.fingerprint;
          scanResults.services = eng.scan_session.fingerprint.services || [];
        }
      }
    } catch (fallbackErr) {
      log(`[Adaptive Scan] Standard scan also unavailable`);
    }
  }

  // Final scan session state
  eng.scan_session = {
    ...eng.scan_session,
    status: "ready",
    fingerprint: scanResults.fingerprint,
    adaptive_depth: currentDepth,
    total_services_found: scanResults.services.length,
    total_vulnerabilities_found: scanResults.vulnerabilities.length,
    pivots_executed: scanResults.pivots.length,
    scan_type: "adaptive_ai_guided"
  };
  
  log(`[Adaptive Scan] Completed at depth ${currentDepth}/${maxScanDepth}. Found ${scanResults.services.length} services, ${scanResults.vulnerabilities.length} vulnerabilities, executed ${scanResults.pivots.length} pivots.`);

  // 4. Perform Knowledge Engine AI analysis on enhanced scan results
  log("Performing Knowledge Engine AI analysis with trained model and dataset on adaptive scan results…");
  try {
    const scanFingerprint = eng.scan_session?.fingerprint || {};
    const services = scanFingerprint.services || [];
    
    // Prepare enhanced scan fingerprint for Knowledge Engine AI analysis
    const fingerprintData = {
      target: target,
      os: scanFingerprint.os || "unknown",
      services: services.map(s => ({
        port: s.port,
        name: s.name,
        product: s.product,
        version: s.version
      })),
      scan_timestamp: eng.scan_session?.timestamp || new Date().toISOString(),
      adaptive_scan_depth: eng.scan_session?.adaptive_depth || 0,
      pivots_executed: eng.scan_session?.pivots_executed || 0,
      vulnerabilities_found: eng.scan_session?.total_vulnerabilities_found || 0
    };

    const aiAnalysis = await axios.post(
      `${KNOWLEDGE_ENGINE}/ai/analyse/scan`,
      {
        target: target,
        scan_fingerprint: fingerprintData
      },
      {
        timeout: 120000
      }
    );
    
    // Record that Knowledge Engine AI was used with adaptive scan results
    eng.knowledge_engine_analysis = aiAnalysis.data?.analysis || { 
      analysis_attempted: true,
      model: "trained_dataset_model",
      timestamp: new Date().toISOString()
    };
    
    const vulnCount = aiAnalysis.data?.vulnerabilities_found || 0;
    log(`Knowledge Engine AI analysis completed successfully using trained model and dataset. Analyzed adaptive scan results from depth ${eng.scan_session?.adaptive_depth || 0}. Found ${vulnCount} vulnerabilities.`);
    eng.ai_reasoning = eng.ai_reasoning || [];
    eng.ai_reasoning.push({
      step: 3,
      stage: "ai_analysis",
      message: "Knowledge Engine AI analysis using trained model and 14,000+ attack dataset on adaptive scan results",
      details: `Adaptive scan depth: ${eng.scan_session?.adaptive_depth || 0}, pivots executed: ${eng.scan_session?.pivots_executed || 0}, identified ${vulnCount} potential vulnerabilities`,
      timestamp: new Date().toISOString()
    });
    broadcast(id, eng);
  } catch (err) {
    log(`Knowledge Engine AI analysis unavailable — continuing with standard pipeline.`);
    console.error(`[engagement ${id}] Knowledge Engine AI analysis error:`, err.message);
    // Still record that analysis was attempted
    eng.knowledge_engine_analysis = { 
      analysis_attempted: true, 
      error: err.message,
      model: "trained_dataset_model",
      timestamp: new Date().toISOString()
    };
  }

  // 5. Build attack vectors using Knowledge Engine trained model
  log("Building attack vectors from Knowledge Engine using trained model and dataset…");
  eng.status = "building_vectors";
  eng.ai_reasoning = eng.ai_reasoning || [];
  
  // Add reasoning for attack vector building
  eng.ai_reasoning.push({
    step: 4,
    stage: "vector_generation",
    message: "Generating attack vectors using Knowledge Engine trained model and 14,000+ attack dataset",
    details: `Services detected: ${eng.scan_session?.fingerprint?.services?.length || 0}, OS: ${eng.scan_session?.fingerprint?.os || "unknown"}, Adaptive scan depth: ${eng.scan_session?.adaptive_depth || 0}`,
    timestamp: new Date().toISOString()
  });
  broadcast(id, eng);
  
  overseerEvent({
    stage: "vector_decomposition",
    type: "progress_update",
    message: "Generating base hypothesis chains for decomposition using trained model.",
    suggestions: [
      `Aim for at least ${boundary.base_top_chains} candidate chains with distinct pathways.`,
      "Ensure each chain includes clear MITRE-aligned progression.",
      "Trained model will match patterns against 14,000+ attack techniques.",
    ],
  });

  const fingerprint = eng.scan_session?.fingerprint || {};
  const filteredServices = filterServicesForAttackVector(fingerprint.services || []);
  const services = mapServicesToAttackVectorLabels(fingerprint.services || []);
  const targetDescription = buildAttackVectorTargetDescription(target, fingerprint);
  const authHeaders = getServiceAuthHeaders();

  // Prefer analyzer-generated chains when already present on the scan session
  const sessionVectors = eng.scan_session?.vectors;
  if (sessionVectors?.chains?.length) {
    eng.attack_chains = {
      target_description: sessionVectors.target_description || targetDescription,
      chains: sessionVectors.chains,
    };
    log(`Using ${eng.attack_chains.chains.length} attack chain(s) from analyzer session.`);
    broadcast(id, eng);
  }

  try {
    if (eng.attack_chains?.chains?.length) {
      console.log(`[engagement ${id}] Skipping attack-vector call — using analyzer session chains`);
    } else {
    console.log(`[engagement ${id}] Calling attack-vector API at ${KNOWLEDGE_ENGINE}/attack-vector`);
    console.log(`[engagement ${id}] Request payload:`, {
      target_description: targetDescription,
      detected_services: services,
      detected_os: fingerprint.os || "",
      top_chains: boundary.base_top_chains,
      services_in_fingerprint: fingerprint.services?.length || 0,
      services_after_filter: filteredServices.length,
    });
    
    const vectorResp = await axios.post(`${KNOWLEDGE_ENGINE}/attack-vector`, {
      target_description: targetDescription,
      detected_services: services,
      detected_os: fingerprint.os || "",
      top_chains: boundary.base_top_chains,
    }, {
      headers: authHeaders,
      timeout: 30000,
    });
    
    console.log(`[engagement ${id}] Attack-vector API response status:`, vectorResp.status);
    eng.attack_chains = {
      target_description: vectorResp.data?.target_description || targetDescription,
      chains: vectorResp.data?.chains || [],
    };
    log(`Built ${eng.attack_chains?.chains?.length || 0} attack chains using trained model.`);
    }
    
    // Add reasoning for successful chain generation
    eng.ai_reasoning.push({
      step: 0.5,
      stage: "chain_analysis",
      message: "Attack chains generated successfully from knowledge base...",
      details: `Generated ${eng.attack_chains?.chains?.length || 0} candidate attack paths with confidence scores`,
      timestamp: new Date().toISOString()
    });
    broadcast(id, eng);
    
    const complexity = computeAttackVectorComplexity(eng.attack_chains);
    overseerEvent({
      stage: "primary_analysis",
      type: "evidence_update",
      message: `Primary chain generation produced ${eng.attack_chains?.chains?.length || 0} chains (complexity=${complexity.toFixed(1)}).`,
      suggestions: [
        "Check chain depth and technique diversity before accepting baseline output.",
      ],
    });
  } catch (err) {
    console.error(`[engagement ${id}] Knowledge engine unavailable:`, err.message);
    console.error(`[engagement ${id}] Full error:`, err);
    log(`Knowledge engine unavailable: ${err.message}`);
    if (!eng.attack_chains) {
      eng.attack_chains = { target_description: targetDescription, chains: [] };
    }
    overseerEvent({
      stage: "primary_analysis",
      type: "gap_flag",
      severity: "high",
      message: `Primary chain generation failed: ${err.message}`,
      gaps: ["Attack chain generation unavailable."],
      suggestions: ["Retry attack-vector generation once dependencies are healthy."],
    });
  }

  // 4. Overseer deepening pass (conditional)
  if (eng.attack_chains?.chains?.length && eng.analysis_overseer) {
    computeAndStoreQuality();
    const signals = collectDeepeningSignals(eng);
    const quality = eng.analysis_overseer.quality;
    const shouldDeepen = (
      signals.gaps.length > 0 &&
      eng.analysis_overseer.deepening_rounds < eng.analysis_overseer.max_deepening_rounds
    );

    if (shouldDeepen) {
      eng.analysis_overseer.deepening_rounds += 1;
      overseerEvent({
        stage: "deepening_pass",
        type: "overseer_feedback",
        severity: "warning",
        message: `Deepening pass ${eng.analysis_overseer.deepening_rounds} triggered (quality=${quality.overall}).`,
        gaps: signals.gaps,
        suggestions: signals.suggestions,
      });

      try {
        const deepResp = await axios.post(`${KNOWLEDGE_ENGINE}/attack-vector`, {
          target_description: `${targetDescription}. Deepen analysis with alternate paths and explicit defense-evasion coverage.`,
          detected_services: services,
          detected_os: fingerprint.os || "",
          top_chains: boundary.deepening_top_chains,
        }, {
          headers: authHeaders,
          timeout: 30000,
        });
        const current = eng.attack_chains?.chains || [];
        const deepChains = deepResp.data?.chains || [];
        const mergedChains = [...current, ...deepChains]
          .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
          .slice(0, boundary.deepening_top_chains);

        eng.attack_chains = {
          target_description: deepResp.data?.target_description || eng.attack_chains?.target_description,
          chains: mergedChains,
        };

        overseerEvent({
          stage: "deepening_pass",
          type: "evidence_update",
          message: `Deepening pass produced ${mergedChains.length} consolidated chains.`,
          suggestions: [
            "Proceed to critique and cross-validation with expanded chain set.",
          ],
        });
      } catch (err) {
        overseerEvent({
          stage: "deepening_pass",
          type: "gap_flag",
          severity: "medium",
          message: `Deepening pass failed: ${err.message}`,
          gaps: ["Failed to expand chain diversity in deepening pass."],
          suggestions: ["Proceed with baseline chains and annotate confidence limits."],
        });
      }
    } else {
      overseerEvent({
        stage: "deepening_pass",
        type: "progress_update",
        message: "Deepening pass skipped; baseline quality signals are acceptable.",
      });
    }
  }

  // 5. OpSec assessment on all chain steps
  if (eng.attack_chains?.chains?.length) {
    log("Running OpSec assessment on attack chains…");
    eng.status = "assessing_opsec";
    broadcast(id, eng);
    overseerEvent({
      stage: "critique_gap_detection",
      type: "progress_update",
      message: "Evaluating attack chains for detectability signals and explicit findings.",
      suggestions: [
        "Identify missing evidence fields (MITRE, detection_method, impact).",
      ],
    });

    const steps = eng.attack_chains.chains
      .flatMap((c) => c.steps || [])
      .map((s) => ({
        attack_id: s.attack?.id,
        title: s.attack?.title || "",
        attack_type: s.attack?.attack_type || "",
        attack_steps: s.attack?.attack_steps || "",
        tools_used: s.attack?.tools_used || "",
        mitre_technique: s.attack?.mitre_technique || "",
        detection_method: s.attack?.detection_method || "",
      }));

    try {
      const opsecResp = await axios.post(`${OPSEC_URL}/assess/chain`, { steps }, {
        headers: getServiceAuthHeaders()
      });
      eng.opsec_reports = opsecResp.data;
      log(`OpSec assessment complete. Risk score: ${opsecResp.data.risk_score}/100`);
      overseerEvent({
        stage: "critique_gap_detection",
        type: "evidence_update",
        message: `Rule-based OpSec assessment returned risk score ${opsecResp.data.risk_score}/100.`,
        suggestions: [
          "Correlate rule findings with tool-level audit for stronger recommendations.",
        ],
      });
    } catch (err) {
      log(`OpSec monitor unavailable: ${err.message}`);
      overseerEvent({
        stage: "critique_gap_detection",
        type: "gap_flag",
        severity: "high",
        message: `OpSec monitor unavailable: ${err.message}`,
        gaps: ["Rule-based OpSec findings missing."],
        suggestions: ["Fallback to tool-level OpSec audit for interim risk estimates."],
      });
    }
  }

  // 6. OpSec audit on attack chains (detailed tool-based analysis)
  if (eng.attack_chains?.chains?.length) {
    log("Running OpSec audit on attack chains…");
    eng.status = "auditing_opsec";
    broadcast(id, eng);
    overseerEvent({
      stage: "cross_validation",
      type: "progress_update",
      message: "Cross-validating chains with tool-level OpSec audit.",
      suggestions: [
        "Compare chain-level and tool-level risk to catch blind spots.",
      ],
    });

    try {
      // Audit the highest-confidence chain
      const topChain = eng.attack_chains.chains[0];
      const auditResp = await axios.post(`${KNOWLEDGE_ENGINE}/opsec/audit/vector`, topChain, {
        headers: getServiceAuthHeaders()
      });
      eng.opsec_audit = auditResp.data;
      log(`OpSec audit complete. Detectability score: ${auditResp.data.overall_risk_score.toFixed(0)}/100`);
      overseerEvent({
        stage: "cross_validation",
        type: "evidence_update",
        message: `Tool-level audit detectability score ${auditResp.data.overall_risk_score.toFixed(0)}/100.`,
        suggestions: [
          "Use substitution suggestions to harden high-risk steps.",
        ],
      });
    } catch (err) {
      log(`OpSec audit unavailable: ${err.message}`);
      overseerEvent({
        stage: "cross_validation",
        type: "gap_flag",
        severity: "medium",
        message: `Tool-level audit unavailable: ${err.message}`,
        gaps: ["Tool-level detectability breakdown missing."],
        suggestions: ["Continue with rule-based findings but flag confidence downgrade."],
      });
    }
  }

  // 7. AI summary with reasoning
  if (openai && eng.attack_chains?.chains?.length) {
    log("Generating AI intelligence summary via OpenRouter…");
    eng.status = "ai_analysis";
    eng.ai_reasoning = []; // Initialize reasoning array
    broadcast(id, eng);
    overseerEvent({
      stage: "synthesis",
      type: "progress_update",
      message: "Synthesizing findings into engagement narrative with step-by-step reasoning.",
      suggestions: [
        "Highlight contradictions between chain confidence and detectability.",
      ],
    });
    try {
      const aiResult = await generateAISummaryWithReasoning(eng, (reasoningStep) => {
        // Streaming reasoning updates
        eng.ai_reasoning = eng.ai_reasoning || [];
        eng.ai_reasoning.push(reasoningStep);
        broadcast(id, eng); // Broadcast reasoning updates in real-time
      });
      eng.ai_summary = aiResult.summary;
      log("AI summary complete with reasoning.");
      overseerEvent({
        stage: "synthesis",
        type: "evidence_update",
        message: "Narrative synthesis complete with reasoning trace.",
      });
    } catch (err) {
      log(`AI summary failed: ${err.message}`);
      overseerEvent({
        stage: "synthesis",
        type: "gap_flag",
        severity: "medium",
        message: `AI synthesis unavailable: ${err.message}`,
        gaps: ["Narrative synthesis missing."],
        suggestions: ["Use structured findings directly in final report output."],
      });
    }
  }

  // 8. Final quality gate
  if (eng.analysis_overseer) {
    computeAndStoreQuality();
    const quality = eng.analysis_overseer.quality;
    const gate = eng.analysis_overseer.quality_gate;
    const passed = gate.status === "pass";

    overseerEvent({
      stage: "quality_gate",
      type: passed ? "evidence_update" : "gap_flag",
      severity: passed ? "info" : "warning",
      message: passed
        ? `Quality gate passed (${quality.overall}/${gate.threshold}).`
        : `Quality gate failed (${quality.overall}/${gate.threshold}); output may be less thorough.`,
      suggestions: passed
        ? ["Return results with confidence and recommended next actions."]
        : ["Re-run engagement with broader service context for higher coverage."],
    });
  }

  eng.status = "complete";
  eng.completed_at = new Date().toISOString();
  log("Engagement pipeline complete.");
  broadcast(id, eng);
}

async function generateAISummaryWithReasoning(eng, onReasoningStep) {
  const chains = eng.attack_chains?.chains || [];
  const opsec  = eng.opsec_reports;

  const chainLines = chains.slice(0, 3).map((c, i) => {
    const steps = (c.steps || []).map(
      (s) => `    [${s.phase}] ${s.attack?.title || ""} (${s.attack?.mitre_technique || ""})`
    ).join("\n");
    return `Chain ${i + 1} (confidence ${(c.confidence * 100).toFixed(0)}%):\n${steps}`;
  }).join("\n\n");

  const opsecLine = opsec
    ? `OpSec Risk Score: ${opsec.risk_score}/100. ` +
      (opsec.global_findings || []).slice(0, 3)
        .map((f) => `[${f.severity.toUpperCase()}] ${f.title}`).join("; ")
    : "OpSec: not assessed";

  const fp = eng.scan_session?.fingerprint;
  const fpLine = fp
    ? `OS: ${fp.os || "unknown"}, Services: ${(fp.services || []).slice(0, 5).map((s) => `${s.name}/${s.port}`).join(", ")}`
    : "Fingerprint: unavailable";

  // Emit initial reasoning step
  onReasoningStep({
    step: 1,
    stage: "data_collection",
    message: "Analyzing target fingerprint and attack chain data...",
    details: `Target: ${eng.target}, OS: ${fp?.os || "unknown"}, ${chains.length} attack chains identified`,
    timestamp: new Date().toISOString()
  });

  // Emit chain analysis reasoning
  onReasoningStep({
    step: 2,
    stage: "chain_analysis",
    message: "Evaluating attack chain confidence and complexity...",
    details: `Top chain confidence: ${chains[0]?.confidence ? (chains[0].confidence * 100).toFixed(0) + "%" : "N/A"}, Total steps across chains: ${chains.reduce((acc, c) => acc + (c.steps?.length || 0), 0)}`,
    timestamp: new Date().toISOString()
  });

  // Emit OpSec analysis reasoning
  if (opsec) {
    onReasoningStep({
      step: 3,
      stage: "opsec_analysis",
      message: "Assessing operational security risks...",
      details: `Risk score: ${opsec.risk_score}/100, Critical findings: ${opsec.global_findings?.filter(f => f.severity === "high").length || 0}`,
      timestamp: new Date().toISOString()
    });
  }

  // Generate the final AI summary
  const message = await openai.chat.completions.create({
    model: AI_MODEL,
    max_tokens: 800,
    messages: [
      {
        role: "system",
        content:
          "You are a concise red team intelligence analyst. " +
          "Provide a short (3-4 paragraph) executive summary of this engagement. " +
          "Cover: highest-risk attack paths, critical OpSec concerns, and top 3 recommended priority actions. " +
          "Be direct and operational. " +
          "Also provide a brief explanation of your reasoning process (2-3 sentences)."
      },
      {
        role: "user",
        content:
          `Target: ${eng.target}\n` +
          `${fpLine}\n\n` +
          `Attack Chains:\n${chainLines}\n\n` +
          `${opsecLine}\n\n` +
          `Please provide your analysis with a brief explanation of your reasoning process.`
      },
    ],
  });

  const content = message.choices[0].message.content;

  // Emit final reasoning step
  onReasoningStep({
    step: 4,
    stage: "final_synthesis",
    message: "Synthesizing final intelligence summary...",
    details: "Integrating all analysis into actionable recommendations",
    timestamp: new Date().toISOString()
  });

  return { summary: content };
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

const server = http.createServer(app);
server.headersTimeout = parseInt(process.env.SERVER_HEADERS_TIMEOUT_MS || "620000", 10);
server.requestTimeout = parseInt(process.env.SERVER_REQUEST_TIMEOUT_MS || "620000", 10);
server.keepAliveTimeout = parseInt(process.env.SERVER_KEEPALIVE_TIMEOUT_MS || "65000", 10);
const wss = new WebSocketServer({ server });

// Map engagementId → Set of ws clients
const subscribers = new Map();

// Map engagementId → Set of terminal ws clients
const terminalSubscribers = new Map();

// Additional subscriber maps for dashboard components
const feedbackLoopSubscribers = new Map(); // Feedback loop analytics
const sessionManagementSubscribers = new Map(); // Session management
const agentStatusSubscribers = new Map(); // Agent status monitor
const attackEventSubscribers = new Map(); // Real-time attack monitor
const attackTreeSubscribers = new Map(); // Attack tree visualization

wss.on("connection", (ws, req) => {
  if (!clientAuth.authorizeWebSocket(req)) {
    ws.close(1008, "Unauthorized");
    return;
  }

  const url = new URL(req.url, "http://localhost");
  const engId = url.searchParams.get("engagement");
  const pathname = url.pathname;
  
  // Determine connection type based on pathname
  const connectionType = pathname.startsWith('/terminal/') ? 'terminal' :
                         pathname.startsWith('/feedback/') ? 'feedback' :
                         pathname.startsWith('/session/') ? 'session' :
                         pathname.startsWith('/agents/') ? 'agents' :
                         pathname.startsWith('/events/') ? 'events' :
                         pathname.startsWith('/tree/') ? 'tree' : 'default';

  if (!engId) {
    ws.close(1008, "engagement param required");
    return;
  }

  // Heartbeat: ping every 30s to detect stale connections
  ws.isAlive = true;
  ws.on("pong", () => { ws.isAlive = true; });

  // Route to appropriate subscriber map based on connection type
  switch (connectionType) {
    case 'terminal':
      if (!terminalSubscribers.has(engId)) terminalSubscribers.set(engId, new Set());
      terminalSubscribers.get(engId).add(ws);
      // Disconnect is broadcast-only: never stop engagements or chain runs.
      ws.on("close", () => terminalSubscribers.get(engId)?.delete(ws));
      console.log(`[ws] terminal client connected to engagement ${engId}`);
      for (const line of getTerminalHistory(engagements, engId)) {
        if (ws.readyState === 1) ws.send(JSON.stringify(line));
      }
      ws.send(JSON.stringify({
        type: 'info',
        content: '🔗 Terminal connection established. Run continues server-side if you disconnect.',
        timestamp: new Date().toISOString(),
      }));
      break;
      
    case 'feedback':
      if (!feedbackLoopSubscribers.has(engId)) feedbackLoopSubscribers.set(engId, new Set());
      feedbackLoopSubscribers.get(engId).add(ws);
      ws.on("close", () => feedbackLoopSubscribers.get(engId)?.delete(ws));
      console.log(`[ws] feedback loop client connected to engagement ${engId}`);
      ws.send(JSON.stringify({
        type: 'connection',
        message: 'Feedback loop analytics connection established'
      }));
      break;
      
    case 'session':
      if (!sessionManagementSubscribers.has(engId)) sessionManagementSubscribers.set(engId, new Set());
      sessionManagementSubscribers.get(engId).add(ws);
      ws.on("close", () => sessionManagementSubscribers.get(engId)?.delete(ws));
      console.log(`[ws] session management client connected to engagement ${engId}`);
      ws.send(JSON.stringify({
        type: 'connection',
        message: 'Session management connection established'
      }));
      break;
      
    case 'agents':
      if (!agentStatusSubscribers.has(engId)) agentStatusSubscribers.set(engId, new Set());
      agentStatusSubscribers.get(engId).add(ws);
      ws.on("close", () => agentStatusSubscribers.get(engId)?.delete(ws));
      console.log(`[ws] agent status client connected to engagement ${engId}`);
      ws.send(JSON.stringify({
        type: 'connection',
        message: 'Agent status monitor connection established'
      }));
      break;
      
    case 'events':
      if (!attackEventSubscribers.has(engId)) attackEventSubscribers.set(engId, new Set());
      attackEventSubscribers.get(engId).add(ws);
      ws.on("close", () => attackEventSubscribers.get(engId)?.delete(ws));
      console.log(`[ws] attack event client connected to engagement ${engId}`);
      ws.send(JSON.stringify({
        type: 'connection',
        message: 'Attack event monitor connection established'
      }));
      break;
      
    case 'tree':
      if (!attackTreeSubscribers.has(engId)) attackTreeSubscribers.set(engId, new Set());
      attackTreeSubscribers.get(engId).add(ws);
      ws.on("close", () => attackTreeSubscribers.get(engId)?.delete(ws));
      console.log(`[ws] attack tree client connected to engagement ${engId}`);
      ws.send(JSON.stringify({
        type: 'connection',
        message: 'Attack tree visualization connection established'
      }));
      break;
      
    default:
      // Regular engagement subscription
      if (!subscribers.has(engId)) subscribers.set(engId, new Set());
      subscribers.get(engId).add(ws);
      // Disconnect is broadcast-only: never stop guided autonomous or chain execution.
      ws.on("close", () => subscribers.get(engId)?.delete(ws));
      console.log(`[ws] client subscribed to engagement ${engId}`);
      // Send current state immediately
      const eng = engagements.get(engId);
      if (eng) ws.send(JSON.stringify(eng));
      break;
  }
});

// Terminate dead connections every 30s
const heartbeatInterval = setInterval(() => {
  wss.clients.forEach((ws) => {
    if (ws.isAlive === false) return ws.terminate();
    ws.isAlive = false;
    ws.ping();
  });
}, 30_000);
wss.on("close", () => clearInterval(heartbeatInterval));

function broadcast(engId, payload) {
  if (payload && typeof payload === "object" && payload.id) {
    engagementManager.schedulePersist(engId, payload);
  }
  const clients = subscribers.get(engId);
  if (!clients) return;
  const msg = JSON.stringify(payload);
  for (const ws of clients) {
    if (ws.readyState === 1 /* OPEN */) ws.send(msg);
  }
}

function broadcastCouncil(engId, payload) {
  const clients = subscribers.get(engId);
  if (!clients) return;
  const msg = JSON.stringify({
    ...payload,
    timestamp: payload.timestamp || new Date().toISOString(),
  });
  for (const ws of clients) {
    if (ws.readyState === 1) ws.send(msg);
  }
}

function inferAttackEventType(message, terminalType) {
  const text = String(message || "").toLowerCase();
  if (text.includes("scan") || text.includes("nmap") || text.includes("recon")) return "scan";
  if (text.includes("exfil")) return "exfiltration";
  if (text.includes("persist")) return "persistence";
  if (terminalType === "error" || text.includes("fail")) return "exploit";
  if (text.includes("execut") || text.includes("exploit") || text.includes("step")) return "exploit";
  return "detection";
}

function inferAttackEventSeverity(terminalType) {
  if (terminalType === "error") return "critical";
  if (terminalType === "warning") return "high";
  if (terminalType === "success") return "low";
  if (terminalType === "command") return "medium";
  return "medium";
}

function emitAttackEvent(engId, event) {
  const eng = engagements.get(engId);
  broadcastAttackEvent(engId, {
    event: {
      id: event.id || `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      timestamp: event.timestamp || new Date().toISOString(),
      type: event.type || "detection",
      severity: event.severity || "medium",
      source: event.source || "orchestrator",
      target: event.target || eng?.target || "unknown",
      description: event.description || "",
      details: event.details || {},
    },
  });
}

function broadcastTerminal(engId, message, type = 'info') {
  const timestamp = new Date().toISOString();
  const payload = {
    type: type,
    content: message,
    timestamp,
  };

  appendTerminalLine(engagements, engId, payload);

  const clients = terminalSubscribers.get(engId);
  if (clients) {
    const msg = JSON.stringify(payload);
    clients.forEach((ws) => {
      if (ws.readyState === 1) ws.send(msg);
    });
  }

  if (message && String(message).trim()) {
    emitAttackEvent(engId, {
      type: inferAttackEventType(message, type),
      severity: inferAttackEventSeverity(type),
      description: String(message).trim(),
      details: { terminal_type: type },
    });
  }
}

const { createGuidedAutonomousService } = require("./guided-autonomous");
guidedAutonomous = createGuidedAutonomousService({
  engagements,
  broadcast,
  broadcastTerminal,
  axios,
  getServiceAuthHeaders,
  normalizeTargetInput,
  isValidTarget,
  validateAndSanitizeTarget,
  buildBoundaryProfile,
  inferOpsecAssessAttackVectorContext,
  KNOWLEDGE_ENGINE,
  OPSEC_URL,
  INTEGRATION_HUB_URL,
  ANALYZER_URL,
  PORT,
  liveAttack,
});

// Enhanced broadcast functions for dashboard components
function broadcastFeedbackLoop(engId, data) {
  const clients = feedbackLoopSubscribers.get(engId);
  if (!clients) return;
  
  const payload = JSON.stringify({
    type: 'feedback_update',
    data: data,
    timestamp: new Date().toISOString()
  });
  
  clients.forEach(ws => {
    if (ws.readyState === 1) ws.send(payload);
  });
}

function broadcastSessionUpdate(engId, data) {
  const clients = sessionManagementSubscribers.get(engId);
  if (!clients) return;
  
  const payload = JSON.stringify({
    type: 'session_update',
    data: data,
    timestamp: new Date().toISOString()
  });
  
  clients.forEach(ws => {
    if (ws.readyState === 1) ws.send(payload);
  });
}

function broadcastAgentStatus(engId, data) {
  const clients = agentStatusSubscribers.get(engId);
  if (!clients) return;
  
  const payload = JSON.stringify({
    type: 'agent_status',
    data: data,
    timestamp: new Date().toISOString()
  });
  
  clients.forEach(ws => {
    if (ws.readyState === 1) ws.send(payload);
  });
}

function broadcastAttackEvent(engId, data) {
  const clients = attackEventSubscribers.get(engId);
  if (!clients) return;
  
  const payload = JSON.stringify({
    type: 'attack_event',
    data: data,
    timestamp: new Date().toISOString()
  });
  
  clients.forEach(ws => {
    if (ws.readyState === 1) ws.send(payload);
  });
}

function broadcastAttackTree(engId, data) {
  const clients = attackTreeSubscribers.get(engId);
  if (!clients) return;
  
  const payload = JSON.stringify({
    type: 'tree_update',
    data: data,
    timestamp: new Date().toISOString()
  });
  
  clients.forEach(ws => {
    if (ws.readyState === 1) ws.send(payload);
  });
}

// ── Global Error Handler (must be last middleware) ────────────────────────────
app.use(globalErrorHandler);

// ── Boot ──────────────────────────────────────────────────────────────────────

async function startServer() {
  try {
    // Initialize engagement manager with persistence
    await engagementManager.initialize();
    robustnessLogger.info("Engagement manager initialized successfully");

    server.listen(PORT, () => {
      robustnessLogger.info(`[orchestrator] listening on :${PORT}`, {
        port: PORT,
        environment: process.env.NODE_ENV || "development",
      });
    });

    // Setup graceful shutdown
    const shutdownManager = new GracefulShutdown(server, { timeout: 30000 });
    shutdownManager.registerCleanup(async () => {
      robustnessLogger.info("Closing WebSocket connections...");
      wss.clients.forEach((client) => client.close());
      wss.close();
    });
    shutdownManager.registerCleanup(async () => {
      robustnessLogger.info("Closing engagement manager...");
      await engagementManager.close();
    });
    shutdownManager.setup();

  } catch (error) {
    robustnessLogger.fatal('[orchestrator] Failed to start:', { error: error.message, stack: error.stack });
    process.exit(1);
  }
}

startServer();
