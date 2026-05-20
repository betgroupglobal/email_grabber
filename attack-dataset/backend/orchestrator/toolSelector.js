"use strict";

const { HUB_OPERATION_ALIASES } = require("./toolCatalog");

const GUIDED_MAX_TOOLS_DEFAULT = parseInt(process.env.GUIDED_MAX_TOOLS_PER_PHASE || "3", 10);
const GUIDED_MAX_TOOLS_HIGH_AGGRESSION = parseInt(
  process.env.GUIDED_MAX_TOOLS_HIGH_AGGRESSION || "4",
  10
);

function targetUrl(target) {
  const t = String(target || "").trim();
  if (!t) return "";
  if (/^https?:\/\//i.test(t)) return t;
  return `https://${t.replace(/^\/+/, "")}`;
}

function priorTextMentions(priorFindings, patterns) {
  const text = String(priorFindings || "").toLowerCase();
  return patterns.some((p) => text.includes(p));
}

function hubOpCoveredByTools(tools, operation) {
  const alias = HUB_OPERATION_ALIASES[operation];
  if (!alias) return false;
  return (tools || []).some(
    (t) =>
      String(t.plugin || "").toLowerCase() === alias.plugin ||
      (t.params?.scan_type && alias.params?.scan_type === t.params.scan_type)
  );
}

/**
 * Rank tools for a guided phase with suggested params.
 */
function rankToolsForPhase(opts = {}) {
  const {
    phaseNum,
    target,
    targetClass = "web_application",
    fingerprint = {},
    aggression = 5,
    webOnly = true,
    catalog = null,
    completedOps = new Set(),
    priorFindings = "",
  } = opts;

  const maxTools =
    aggression >= 7 ? GUIDED_MAX_TOOLS_HIGH_AGGRESSION : GUIDED_MAX_TOOLS_DEFAULT;
  const url = targetUrl(target);
  const isWeb =
    webOnly ||
    targetClass === "web_application" ||
    targetClass === "ecommerce";
  const hasRecon = priorTextMentions(priorFindings, [
    "analyzer:",
    "hub reconnaissance",
    "nmap:",
    "web ports",
    "port 80",
    "port 443",
  ]);
  const hasVulnScan = priorTextMentions(priorFindings, [
    "nuclei:",
    "critical",
    "cve-",
    "ffuf:",
  ]);
  const hasForms = priorTextMentions(priorFindings, [
    "form",
    "parameter",
    "sqlmap",
    "inject",
    "login",
    "cart",
    "checkout",
  ]);

  const candidates = [];

  const push = (entry, score, rationale) => {
    candidates.push({
      id: entry.id,
      plugin: entry.plugin,
      tool: entry.tool,
      params: { ...entry.params },
      rationale,
      score,
    });
  };

  const healthy = (plugin) => {
    if (!catalog?.entries) return true;
    const e = catalog.entries.find(
      (x) => String(x.plugin).toLowerCase() === String(plugin).toLowerCase()
    );
    return !e || (e.enabled !== false && e.healthy !== false);
  };

  switch (phaseNum) {
    case 1:
      if (healthy("analyzer")) {
        push(
          {
            id: "analyzer:scan:web_application",
            plugin: "analyzer",
            tool: "scan",
            params: { scan_type: "web_application", scan_timeout_sec: 120 },
          },
          70,
          "Initial web-oriented fingerprint"
        );
      }
      break;

    case 2:
      if (!hasRecon && healthy("analyzer")) {
        push(
          {
            id: "analyzer:scan:web_application",
            plugin: "analyzer",
            tool: "scan",
            params: { scan_type: "web_application", scan_timeout_sec: 180 },
          },
          90,
          "Recon — analyzer web scan (avoid repeat if prior recon present)"
        );
      }
      if (!completedOps.has("reconnaissance") && !hubOpCoveredByTools(candidates, "reconnaissance")) {
        push(
          {
            id: "hub:recon",
            plugin: "nmap",
            tool: "reconnaissance",
            operation: "reconnaissance",
            params: { ports: "80,443,8080,8443", scan_type: "web_application" },
          },
          hasRecon ? 40 : 85,
          "Hub nmap 80/443 focused"
        );
      }
      if (isWeb && healthy("nuclei")) {
        push(
          {
            id: "nuclei:scan_target",
            plugin: "nuclei",
            tool: "scan_target",
            params: {
              operation: "scan_target",
              target: url,
              templates: "http/technologies/",
              severity: "info,low,medium",
            },
          },
          75,
          "Technology fingerprint templates"
        );
      }
      break;

    case 3:
      if (healthy("nuclei")) {
        push(
          {
            id: "nuclei:scan_target",
            plugin: "nuclei",
            tool: "scan_target",
            params: {
              operation: "scan_target",
              target: url,
              severity: "critical,high,medium",
              tags: "cve,http",
            },
          },
          95,
          "CVE/high severity nuclei pass"
        );
      }
      if (isWeb && healthy("ffuf")) {
        push(
          {
            id: "ffuf:fuzz_url",
            plugin: "ffuf",
            tool: "fuzz_url",
            params: { operation: "fuzz_url", url },
          },
          80,
          "Directory discovery"
        );
        if (!hasVulnScan) {
          push(
            {
              id: "ffuf:fuzz_vhost",
              plugin: "ffuf",
              tool: "fuzz_vhost",
              params: { operation: "fuzz_vhost", url },
            },
            65,
            "Vhost discovery for CDN/multi-host"
          );
        }
      }
      break;

    case 4:
      if (healthy("knowledge_engine")) {
        push(
          {
            id: "ke:attack-vector",
            plugin: "knowledge_engine",
            tool: "attack-vector",
            params: { top_chains: aggression >= 7 ? 3 : 2 },
          },
          88,
          "MITRE-aligned chains from dataset"
        );
      }
      if (isWeb && hasForms && healthy("sqlmap") && aggression >= 5) {
        push(
          {
            id: "sqlmap:test_url",
            plugin: "sqlmap",
            tool: "test_url",
            params: {
              operation: "test_url",
              target: url,
              level: aggression >= 7 ? 2 : 1,
              risk: 1,
            },
          },
          82,
          "SQLi probe — prior findings suggest forms/parameters"
        );
      } else if (isWeb && healthy("nuclei") && !hasVulnScan) {
        push(
          {
            id: "nuclei:scan_target",
            plugin: "nuclei",
            tool: "scan_target",
            params: {
              operation: "scan_target",
              target: url,
              severity: "medium,high,critical",
            },
          },
          70,
            "Web template scan before assess"
        );
      }
      break;

    case 5:
      if (isWeb && hasForms && healthy("sqlmap") && aggression >= 7) {
        push(
          {
            id: "sqlmap:test_url",
            plugin: "sqlmap",
            tool: "test_url",
            params: { operation: "test_url", target: url, level: 1, risk: 1 },
          },
          60,
          "Exploitation-phase sqlmap if parameters seen"
        );
      }
      break;

    default:
      break;
  }

  candidates.sort((a, b) => (b.score || 0) - (a.score || 0));

  const cap = aggression <= 4 ? Math.min(2, maxTools) : maxTools;
  return candidates.slice(0, cap).map(({ score, ...rest }) => rest);
}

/**
 * Clear redundant invoke_hub when tools_to_invoke already cover the operation.
 */
function dedupeHubFromPlan(plan) {
  if (!plan || !Array.isArray(plan.tools_to_invoke) || !plan.tools_to_invoke.length) {
    return plan;
  }
  const op = plan.hub_operation;
  if (!op || op === "none") return plan;
  if (hubOpCoveredByTools(plan.tools_to_invoke, op)) {
    return {
      ...plan,
      invoke_hub: false,
      hub_operation: "none",
      hub_parameters: {},
    };
  }
  return plan;
}

module.exports = {
  rankToolsForPhase,
  dedupeHubFromPlan,
  targetUrl,
};
