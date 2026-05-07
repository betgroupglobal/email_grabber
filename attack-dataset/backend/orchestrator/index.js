"use strict";
require("dotenv").config();
const express = require("express");
const http = require("http");
const { WebSocketServer } = require("ws");
const { v4: uuidv4 } = require("uuid");
const axios = require("axios");

const KNOWLEDGE_ENGINE = process.env.KNOWLEDGE_ENGINE_URL || "http://localhost:8000";
const ANALYZER_URL     = process.env.ANALYZER_URL         || "http://localhost:8001";
const OPSEC_URL        = process.env.OPSEC_URL            || "http://localhost:8002";
const PORT             = parseInt(process.env.PORT || "3001");

const app = express();
app.use(express.json());

// ── CORS (dev) ────────────────────────────────────────────────────────────────
app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

// ── In-memory engagement store ────────────────────────────────────────────────
const engagements = new Map();

// ── HTTP routes ───────────────────────────────────────────────────────────────

app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "orchestrator" });
});

/**
 * POST /engage
 * Kick off a full engagement pipeline for a target:
 *   1. Start real-time scan (analyzer)
 *   2. Return engagement ID immediately
 *   3. Push updates over WebSocket
 */
app.post("/engage", async (req, res) => {
  const { target } = req.body;
  if (!target) return res.status(400).json({ error: "target required" });

  const engagementId = uuidv4().slice(0, 8);
  const engagement = {
    id: engagementId,
    target,
    status: "starting",
    scan_session: null,
    attack_chains: null,
    opsec_reports: null,
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
    const { data } = await axios.post(`${KNOWLEDGE_ENGINE}/search`, req.body);
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
    const { data } = await axios.post(`${KNOWLEDGE_ENGINE}/attack-vector`, req.body);
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "knowledge engine unavailable" });
  }
});

/**
 * POST /opsec/assess
 * Proxy to OpSec Monitor.
 */
app.post("/opsec/assess", async (req, res) => {
  try {
    const { data } = await axios.post(`${OPSEC_URL}/assess`, req.body);
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "opsec monitor unavailable" });
  }
});

/**
 * POST /opsec/chain
 * Assess a full attack chain via OpSec Monitor.
 */
app.post("/opsec/chain", async (req, res) => {
  try {
    const { data } = await axios.post(`${OPSEC_URL}/assess/chain`, req.body);
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "opsec monitor unavailable" });
  }
});

// ── Pipeline ──────────────────────────────────────────────────────────────────

async function runEngagementPipeline(id, target) {
  const eng = engagements.get(id);

  function log(msg) {
    console.log(`[engagement ${id}] ${msg}`);
    eng.log.push({ ts: new Date().toISOString(), msg });
    broadcast(id, eng);
  }

  // 1. Kick off scan
  log(`Starting scan of ${target}…`);
  eng.status = "scanning";
  broadcast(id, eng);

  let scanResp;
  try {
    scanResp = await axios.post(`${ANALYZER_URL}/scan`, { target });
  } catch (err) {
    log(`Analyzer unavailable — skipping live scan, building vectors from description only.`);
    // Fall through with empty fingerprint
    scanResp = { data: { id: null, status: "skipped" } };
  }

  const sessionId = scanResp.data.id;
  eng.scan_session = scanResp.data;

  // 2. Poll scan until complete (or timeout 120s)
  if (sessionId) {
    log(`Scan session ${sessionId} started. Polling for completion…`);
    const deadline = Date.now() + 120_000;
    while (Date.now() < deadline) {
      await sleep(2000);
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
    log(`Scan completed with status: ${eng.scan_session?.status || "unknown"}`);
  }

  // 3. Build attack vectors
  log("Building attack vectors from Knowledge Engine…");
  eng.status = "building_vectors";
  broadcast(id, eng);

  const services = eng.scan_session?.fingerprint?.services?.map(
    (s) => [s.name, s.product, s.version].filter(Boolean).join(" ")
  ) || [];

  try {
    const vectorResp = await axios.post(`${KNOWLEDGE_ENGINE}/attack-vector`, {
      target_description: `Target: ${target}. OS: ${eng.scan_session?.fingerprint?.os || "unknown"}`,
      detected_services: services,
      detected_os: eng.scan_session?.fingerprint?.os || "",
      top_chains: 3,
    });
    eng.attack_chains = vectorResp.data;
    log(`Built ${eng.attack_chains?.chains?.length || 0} attack chains.`);
  } catch (err) {
    log(`Knowledge engine unavailable: ${err.message}`);
  }

  // 4. OpSec assessment on all chain steps
  if (eng.attack_chains?.chains?.length) {
    log("Running OpSec assessment on attack chains…");
    eng.status = "assessing_opsec";
    broadcast(id, eng);

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
      const opsecResp = await axios.post(`${OPSEC_URL}/assess/chain`, { steps });
      eng.opsec_reports = opsecResp.data;
      log(`OpSec assessment complete. Risk score: ${opsecResp.data.risk_score}/100`);
    } catch (err) {
      log(`OpSec monitor unavailable: ${err.message}`);
    }
  }

  eng.status = "complete";
  eng.completed_at = new Date().toISOString();
  log("Engagement pipeline complete.");
  broadcast(id, eng);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

const server = http.createServer(app);
const wss = new WebSocketServer({ server });

// Map engagementId → Set of ws clients
const subscribers = new Map();

wss.on("connection", (ws, req) => {
  const url = new URL(req.url, "http://localhost");
  const engId = url.searchParams.get("engagement");

  if (!engId) {
    ws.close(1008, "engagement param required");
    return;
  }

  if (!subscribers.has(engId)) subscribers.set(engId, new Set());
  subscribers.get(engId).add(ws);

  // Send current state immediately
  const eng = engagements.get(engId);
  if (eng) ws.send(JSON.stringify(eng));

  ws.on("close", () => {
    subscribers.get(engId)?.delete(ws);
  });

  console.log(`[ws] client subscribed to engagement ${engId}`);
});

function broadcast(engId, payload) {
  const clients = subscribers.get(engId);
  if (!clients) return;
  const msg = JSON.stringify(payload);
  for (const ws of clients) {
    if (ws.readyState === 1 /* OPEN */) ws.send(msg);
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────

server.listen(PORT, () => {
  console.log(`[orchestrator] listening on :${PORT}`);
});
