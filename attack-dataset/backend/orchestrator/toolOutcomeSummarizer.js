"use strict";

const MAX_BLOCK_CHARS = 4000;

function safeJsonSlice(obj, max = 1200) {
  try {
    return JSON.stringify(obj).slice(0, max);
  } catch {
    return String(obj).slice(0, max);
  }
}

function extractPaths(text) {
  const paths = new Set();
  const re = /(?:\/[\w.-]+){1,8}/g;
  let m;
  while ((m = re.exec(text)) && paths.size < 12) {
    const p = m[0];
    if (p.length > 2 && p !== "/") paths.add(p);
  }
  return [...paths];
}

function summarizeNuclei(output) {
  const text =
    typeof output === "string" ? output : safeJsonSlice(output?.findings || output);
  const critical = (text.match(/critical/gi) || []).length;
  const high = (text.match(/\bhigh\b/gi) || []).length;
  const cve = [...new Set((text.match(/CVE-\d{4}-\d+/gi) || []))].slice(0, 5);
  const templates = (text.match(/\[([^\]]+)\]/g) || []).slice(0, 3);
  const parts = [];
  if (critical || high) parts.push(`${critical} critical, ${high} high`);
  if (cve.length) parts.push(`CVEs: ${cve.join(", ")}`);
  if (templates.length) parts.push(`templates: ${templates.join(" ")}`);
  if (!parts.length && text.length > 20) parts.push("scan completed (parse raw output)");
  return parts.length ? `nuclei: ${parts.join("; ")}` : null;
}

function summarizeFfuf(output) {
  const text = typeof output === "string" ? output : safeJsonSlice(output);
  const paths = extractPaths(text);
  const status200 = (text.match(/200/g) || []).length;
  if (!paths.length && !status200) return text.length > 30 ? "ffuf: completed (no notable paths in summary)" : null;
  return `ffuf: ${paths.length ? `paths ${paths.slice(0, 8).join(", ")}` : ""}${status200 ? ` (${status200} 200-responses)` : ""}`.trim();
}

function summarizeSqlmap(output) {
  const text = typeof output === "string" ? output : safeJsonSlice(output);
  if (/injectable|vulnerable|Parameter:/i.test(text)) {
    return `sqlmap: possible injection — ${text.slice(0, 200)}`;
  }
  if (/not injectable|all tested parameters/i.test(text)) return "sqlmap: no injection found (level 1)";
  return text.length > 40 ? `sqlmap: ${text.slice(0, 180)}` : null;
}

function summarizeAnalyzer(output, result) {
  const fp = output?.fingerprint || result?.fingerprint || output;
  if (!fp || typeof fp !== "object") return null;
  const services = fp.services || [];
  const webPorts = services
    .filter((s) => ["80", "443", "8080", "8443"].includes(String(s.port)))
    .map((s) => `${s.port}/${s.name || "tcp"}`)
    .slice(0, 6);
  const ip = fp.ip || fp.target;
  const lines = [];
  if (ip) lines.push(`target IP ${ip}`);
  if (webPorts.length) lines.push(`web ports: ${webPorts.join(", ")}`);
  else if (services.length) {
    const ports = services.slice(0, 8).map((s) => s.port).join(",");
    lines.push(`${services.length} services (sample ports: ${ports})`);
  }
  return lines.length ? `analyzer: ${lines.join("; ")}` : null;
}

function summarizeKnowledgeEngine(output) {
  const chains = output?.chains || output?.attack_chains?.chains;
  if (!Array.isArray(chains) || !chains.length) return null;
  const titles = chains
    .slice(0, 3)
    .map((c) => c.steps?.[0]?.attack?.title || c.chain_id || "chain")
    .filter(Boolean);
  return `knowledge_engine: ${chains.length} chain(s) — ${titles.join("; ")}`;
}

function summarizeHubResult(hubEntry) {
  if (!hubEntry) return null;
  if (hubEntry.error) return `hub ${hubEntry.operation}: failed — ${hubEntry.error}`;
  const op = hubEntry.operation || "hub";
  const data = hubEntry.result;
  const out = data?.output ?? data;
  if (op === "reconnaissance" && out?.fingerprint) {
    return summarizeAnalyzer(out, data) || `hub reconnaissance: ${safeJsonSlice(out, 400)}`;
  }
  const text = typeof out === "string" ? out : safeJsonSlice(out, 600);
  return text.length > 10 ? `hub ${op}: ${text.slice(0, 500)}` : null;
}

function summarizeSingleToolResult(tr) {
  if (!tr) return null;
  const plugin = String(tr.plugin || "").toLowerCase();
  const out = tr.result?.output ?? tr.result;
  if (!tr.success) {
    return `${plugin}/${tr.tool || "?"}: failed — ${tr.error || "unknown"}`;
  }
  switch (plugin) {
    case "nuclei":
      return summarizeNuclei(out);
    case "ffuf":
      return summarizeFfuf(out);
    case "sqlmap":
      return summarizeSqlmap(out);
    case "analyzer":
      return summarizeAnalyzer(out, tr.result);
    case "knowledge_engine":
      return summarizeKnowledgeEngine(out);
    case "nmap":
      return out ? `nmap: ${safeJsonSlice(out, 300)}` : null;
    default:
      if (typeof out === "string" && out.length > 20) {
        return `${plugin}: ${out.slice(0, 280)}`;
      }
      if (out && typeof out === "object") {
        return `${plugin}: ${safeJsonSlice(out, 280)}`;
      }
      return tr.success ? `${plugin}: ok` : null;
  }
}

/**
 * Build structured findings block from tool + hub execution results.
 */
function summarizeToolOutcomes({ tool_results = [], hub_results = [] } = {}) {
  const lines = [];
  for (const tr of tool_results || []) {
    const line = summarizeSingleToolResult(tr);
    if (line) lines.push(line);
  }
  for (const hr of hub_results || []) {
    const line = summarizeHubResult(hr);
    if (line) lines.push(line);
  }
  if (!lines.length) return "";
  return `TOOL OUTCOMES:\n${lines.join("\n")}`;
}

/**
 * Merge plan narrative with synthesized tool outcomes for next-phase context.
 */
function buildPhaseArtifactText(planArtifact, tool_results, hub_results, maxChars = MAX_BLOCK_CHARS) {
  const base = String(planArtifact || "").trim();
  const toolBlock = summarizeToolOutcomes({ tool_results, hub_results });
  if (!toolBlock) return base.slice(0, maxChars);
  const combined = base ? `${base}\n\n${toolBlock}` : toolBlock;
  return combined.slice(0, maxChars);
}

/**
 * Extract prior findings keywords for tool selector (forms, CVEs, paths).
 */
function extractPriorFindingsText(phaseRecords) {
  const chunks = [];
  for (const p of phaseRecords || []) {
    if (p.findings_summary) chunks.push(p.findings_summary);
    if (p.tool_results?.length || p.hub_results?.length) {
      chunks.push(summarizeToolOutcomes(p));
    }
    if (p.artifact_text) chunks.push(p.artifact_text.slice(0, 1500));
  }
  return chunks.join("\n").slice(0, 8000);
}

/**
 * Merge analyzer fingerprint from tool/hub results into ctx.fingerprint.
 */
function mergeFingerprintFromResults(existing, tool_results, hub_results) {
  let fp = existing && typeof existing === "object" ? { ...existing } : {};
  for (const tr of tool_results || []) {
    if (tr.plugin === "analyzer" && tr.success) {
      const out = tr.result?.output || tr.result;
      if (out?.fingerprint) fp = { ...fp, ...out.fingerprint };
      if (out?.vectors) fp.vectors = out.vectors;
    }
  }
  for (const hr of hub_results || []) {
    const data = hr.result;
    const fingerprint = data?.output?.fingerprint || data?.fingerprint;
    if (fingerprint) fp = { ...fp, ...fingerprint, target: fp.target || fingerprint.target };
  }
  return fp;
}

module.exports = {
  summarizeToolOutcomes,
  buildPhaseArtifactText,
  extractPriorFindingsText,
  mergeFingerprintFromResults,
  summarizeSingleToolResult,
};
