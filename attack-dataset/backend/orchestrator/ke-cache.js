"use strict";

const DEFAULT_TTL_MS = Math.max(
  60_000,
  parseInt(process.env.KE_CACHE_TTL_MS || "600000", 10)
);
const MAX_ENTRIES = Math.max(32, parseInt(process.env.KE_CACHE_MAX_ENTRIES || "128", 10));

const searchCache = new Map();
const attackVectorCache = new Map();

function normalizeKey(...parts) {
  return parts
    .map((p) => String(p || "").trim().toLowerCase())
    .filter(Boolean)
    .join(":");
}

function prune(map) {
  if (map.size <= MAX_ENTRIES) return;
  const excess = map.size - MAX_ENTRIES;
  const keys = map.keys();
  for (let i = 0; i < excess; i++) {
    const { value } = keys.next();
    if (value != null) map.delete(value);
  }
}

function cacheGet(map, key) {
  const entry = map.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    map.delete(key);
    return null;
  }
  entry.hits += 1;
  return entry.data;
}

function cacheSet(map, key, data, ttlMs = DEFAULT_TTL_MS) {
  map.set(key, { data, expiresAt: Date.now() + ttlMs, hits: 0 });
  prune(map);
}

function formatSearchHitsForRag(hits, limit = 5) {
  if (!Array.isArray(hits) || !hits.length) return "";
  return hits
    .slice(0, limit)
    .map((h, i) => {
      const rec = h.record || h;
      const title = rec.title || rec.attack_type || rec.id || `record-${i + 1}`;
      const body = (
        rec.description ||
        rec.scenario_description ||
        rec.content ||
        rec.text ||
        ""
      ).slice(0, 480);
      const score = h.score != null ? ` (relevance ${h.score})` : "";
      return `[${i + 1}] ${title}${score}: ${body}`;
    })
    .join("\n");
}

function rerankHitsByTargetKeywords(hits, target) {
  if (!Array.isArray(hits) || !hits.length || !target) return hits;
  const host = String(target)
    .replace(/^https?:\/\//i, "")
    .split("/")[0]
    .toLowerCase();
  const tokens = host
    .replace(/[^a-z0-9.-]+/g, " ")
    .split(/[.\s-]+/)
    .filter((t) => t.length > 2);
  if (!tokens.length) return hits;

  const scored = hits.map((h) => {
    const rec = h.record || h;
    const text = [
      rec.title,
      rec.category,
      rec.attack_type,
      rec.tags,
      rec.mitre_technique,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    let boost = 0;
    for (const tok of tokens) {
      if (text.includes(tok)) boost += 0.15;
    }
    for (const kw of ["web", "http", "https", "owasp", "e-commerce", "api"]) {
      if (text.includes(kw)) boost += 0.04;
    }
    const base = typeof h.score === "number" ? h.score : 0;
    return { hit: h, score: base + boost };
  });
  scored.sort((a, b) => b.score - a.score);
  return scored.map((s) => ({ ...s.hit, score: Math.round(s.score * 10000) / 10000 }));
}

async function getCachedSearch({ query, target, limit = 5, fetchFn, ttlMs }) {
  const key = normalizeKey("search", query, target || "", limit);
  const cached = cacheGet(searchCache, key);
  if (cached) return { ...cached, cache_hit: true };

  const started = Date.now();
  const raw = await fetchFn();
  const latency_ms = Date.now() - started;
  const hits = rerankHitsByTargetKeywords(
    raw?.results || raw?.hits || raw?.matches || [],
    target
  );
  const rag_context = formatSearchHitsForRag(hits, limit);
  const payload = { hits, rag_context, latency_ms, cache_hit: false };
  cacheSet(searchCache, key, payload, ttlMs);
  return payload;
}

async function getCachedAttackVector({ body, fetchFn, ttlMs }) {
  const key = normalizeKey(
    "attack-vector",
    body?.target_description,
    (body?.detected_services || []).join(","),
    body?.detected_os,
    body?.top_chains
  );
  const cached = cacheGet(attackVectorCache, key);
  if (cached) return { ...cached, cache_hit: true };

  const started = Date.now();
  const data = await fetchFn();
  const payload = { data, latency_ms: Date.now() - started, cache_hit: false };
  cacheSet(attackVectorCache, key, payload, ttlMs);
  return payload;
}

function clearKeCache() {
  searchCache.clear();
  attackVectorCache.clear();
}

function keCacheStats() {
  return {
    search_entries: searchCache.size,
    attack_vector_entries: attackVectorCache.size,
    ttl_ms: DEFAULT_TTL_MS,
  };
}

module.exports = {
  DEFAULT_TTL_MS,
  formatSearchHitsForRag,
  rerankHitsByTargetKeywords,
  getCachedSearch,
  getCachedAttackVector,
  clearKeCache,
  keCacheStats,
};
