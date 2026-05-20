"use strict";

/**
 * External tool catalog for AI orchestration — hub plugins + static analyzer/KE tools.
 * Fetched from GET /integrations; cached briefly for prompt injection and validation.
 */

const CATALOG_CACHE_TTL_MS = Math.max(
  5000,
  parseInt(process.env.TOOL_CATALOG_CACHE_MS || "60000", 10)
);

/** @type {{ catalog: object|null, fetchedAt: number }} */
const cache = { catalog: null, fetchedAt: 0 };

const ANALYZER_SCAN_PROFILES = [
  {
    id: "analyzer:scan:quick",
    plugin: "analyzer",
    tool: "scan",
    description: "Quick port/service fingerprint (analyzer POST /scan)",
    params: { scan_type: "quick" },
    web_safe: true,
    destructive: false,
  },
  {
    id: "analyzer:scan:web_application",
    plugin: "analyzer",
    tool: "scan",
    description: "Web application scan profile (HTTP-focused)",
    params: { scan_type: "web_application" },
    web_safe: true,
    destructive: false,
  },
  {
    id: "analyzer:scan:comprehensive",
    plugin: "analyzer",
    tool: "scan",
    description: "Comprehensive scan (broader port/service coverage)",
    params: { scan_type: "comprehensive" },
    web_safe: true,
    destructive: false,
  },
];

const KNOWLEDGE_ENGINE_TOOLS = [
  {
    id: "ke:search",
    plugin: "knowledge_engine",
    tool: "search",
    description: "Semantic search attack dataset (POST /search)",
    params: { top_k: 10 },
    web_safe: true,
    destructive: false,
  },
  {
    id: "ke:attack-vector",
    plugin: "knowledge_engine",
    tool: "attack-vector",
    description: "Generate MITRE-aligned attack chains (POST /attack-vector)",
    params: {},
    web_safe: true,
    destructive: false,
  },
  {
    id: "ke:ml-predict",
    plugin: "knowledge_engine",
    tool: "ml/predict",
    description: "ML category prediction for live query text",
    params: { target: "category", top_k: 5 },
    web_safe: true,
    destructive: false,
  },
];

const WEB_SCANNER_PLUGINS = new Set(["nuclei", "ffuf", "sqlmap"]);
const MCP_BURP_PLUGIN = "mcp_burp";
const SQLMAP_ROE_OPERATIONS = new Set(["test_url", "crawl_and_test"]);

const {
  buildBurpStaticCatalogEntries,
  burpToolRequiresRoe,
  isBurpDestructiveTool,
  isBurpPassiveTool,
  resolveBurpMcpToolName,
} = require("./mcpBurpTools");
const { MCP_BURP_ENABLED, listTools: mcpListTools } = require("./mcpClient");
const { ALLOW_HIGH_RISK } = require("./live-attack/directive-applier");

const BURP_MCP_TOOLS = buildBurpStaticCatalogEntries();

const HUB_OPERATION_ALIASES = {
  reconnaissance: { plugin: "nmap", params: { scan_type: "quick" } },
  port_scan: { plugin: "nmap", params: { scan_type: "quick" } },
  vulnerability_scan: { plugin: "nmap", params: { scan_type: "comprehensive" } },
  nuclei_scan: { plugin: "nuclei", params: { operation: "scan_target", severity: "medium,high,critical" } },
  nuclei_templates: { plugin: "nuclei", params: { operation: "list_templates" } },
  ffuf_fuzz: { plugin: "ffuf", params: { operation: "fuzz_url" } },
  ffuf_vhost: { plugin: "ffuf", params: { operation: "fuzz_vhost" } },
  sqlmap_test: { plugin: "sqlmap", params: { operation: "test_url", level: 1, risk: 1 } },
  sqlmap_crawl: { plugin: "sqlmap", params: { operation: "crawl_and_test", level: 1, risk: 1 } },
  metasploit_list_modules: { plugin: "metasploit", params: { operation: "list_modules" } },
  metasploit_auxiliary: {
    plugin: "metasploit",
    params: {
      operation: "run_auxiliary",
      module: "auxiliary/scanner/http/http_version",
      dry_run: false,
    },
  },
  metasploit_exploit: {
    plugin: "metasploit",
    params: { operation: "run_exploit", dry_run: false },
  },
  metasploit_payload: {
    plugin: "metasploit",
    params: { operation: "generate_payload", dry_run: false },
  },
};

/** Static Metasploit tool entries (merged into catalog even before hub health refresh). */
const NUCLEI_TOOLS = [
  {
    id: "nuclei:scan_target",
    plugin: "nuclei",
    tool: "scan_target",
    description: "Nuclei template scan (JSONL, severity filter)",
    params: { operation: "scan_target", severity: "medium,high,critical" },
    web_safe: true,
    destructive: false,
  },
  {
    id: "nuclei:list_templates",
    plugin: "nuclei",
    tool: "list_templates",
    description: "List available Nuclei templates",
    params: { operation: "list_templates" },
    web_safe: true,
    destructive: false,
  },
];

const FFUF_TOOLS = [
  {
    id: "ffuf:fuzz_url",
    plugin: "ffuf",
    tool: "fuzz_url",
    description: "ffuf directory/parameter fuzz (JSON output)",
    params: { operation: "fuzz_url" },
    web_safe: true,
    destructive: false,
  },
  {
    id: "ffuf:fuzz_vhost",
    plugin: "ffuf",
    tool: "fuzz_vhost",
    description: "ffuf virtual host discovery",
    params: { operation: "fuzz_vhost" },
    web_safe: true,
    destructive: false,
  },
];

const SQLMAP_TOOLS = [
  {
    id: "sqlmap:test_url",
    plugin: "sqlmap",
    tool: "test_url",
    description: "sqlmap injection test (level=1 risk=1, batch)",
    params: { operation: "test_url", level: 1, risk: 1 },
    web_safe: true,
    destructive: false,
  },
  {
    id: "sqlmap:crawl_and_test",
    plugin: "sqlmap",
    tool: "crawl_and_test",
    description: "sqlmap crawl + form test (shallow crawl)",
    params: { operation: "crawl_and_test", level: 1, risk: 1 },
    web_safe: true,
    destructive: false,
  },
];

const METASPLOIT_TOOLS = [
  {
    id: "msf:list_modules",
    plugin: "metasploit",
    tool: "list_modules",
    description: "Search/list Metasploit modules (auxiliary, exploit, payload)",
    params: { operation: "list_modules", module_type: "auxiliary" },
    web_safe: true,
    destructive: false,
  },
  {
    id: "msf:run_auxiliary",
    plugin: "metasploit",
    tool: "run_auxiliary",
    description: "Run Metasploit auxiliary scanner (web-safe modules in web_only)",
    params: {
      operation: "run_auxiliary",
      module: "auxiliary/scanner/http/http_version",
      dry_run: false,
    },
    web_safe: true,
    destructive: false,
  },
  {
    id: "msf:run_exploit",
    plugin: "metasploit",
    tool: "run_exploit",
    description: "Run Metasploit exploit module (live execution when hub configured)",
    params: { operation: "run_exploit", dry_run: false },
    web_safe: false,
    destructive: true,
  },
  {
    id: "msf:generate_payload",
    plugin: "metasploit",
    tool: "generate_payload",
    description: "Generate payload via msfvenom",
    params: { operation: "generate_payload", dry_run: false },
    web_safe: false,
    destructive: true,
  },
];

const DESTRUCTIVE_PLUGINS = new Set(["openvas", "metasploit"]);
const METASPLOIT_DESTRUCTIVE_TOOLS = new Set(["run_exploit", "generate_payload"]);
const DESTRUCTIVE_OPERATIONS = new Set([
  "exploitation",
  "exfiltration",
  "persistence",
  "privilege_escalation",
  "post_exploitation",
]);
const WEB_ONLY_BLOCKED_PLUGINS = new Set(["openvas"]);
const WEB_ONLY_BLOCKED_OPERATIONS = new Set([
  "exploitation",
  "exfiltration",
  "persistence",
  "privilege_escalation",
  "post_exploitation",
]);

function hubPluginToEntry(p) {
  const name = p.name || p.plugin_name;
  if (!name) return null;
  const caps = p.capabilities || p.execution_types || [];
  const isMsf = name === "metasploit";
  return {
    id: `hub:${name}`,
    plugin: name,
    tool: name,
    description: p.description || `${name} integration hub plugin`,
    category: p.category,
    capabilities: caps.length ? caps : isMsf ? METASPLOIT_TOOLS.map((t) => t.tool) : [],
    healthy: p.healthy !== false && p.health_status !== "unhealthy",
    enabled: p.enabled !== false && p.status !== "disabled",
    web_safe: isMsf ? false : !DESTRUCTIVE_PLUGINS.has(name),
    destructive: isMsf || DESTRUCTIVE_PLUGINS.has(name),
  };
}

async function mergeMcpBurpTools(catalog) {
  if (!MCP_BURP_ENABLED()) {
    catalog.mcp_status = { burp_enabled: false };
    return catalog;
  }

  const staticIds = new Set(BURP_MCP_TOOLS.map((e) => e.id));
  const entries = catalog.entries.filter((e) => !String(e.id || "").startsWith("burp:"));
  entries.push(...BURP_MCP_TOOLS);

  let mcpDynamic = [];
  try {
    const { tools, error, degraded } = await mcpListTools("burp");
    mcpDynamic = tools || [];
    catalog.mcp_status = {
      burp_enabled: true,
      tool_count: mcpDynamic.length,
      error: error || null,
      degraded: Boolean(degraded),
    };
    for (const t of mcpDynamic) {
      const name = t.name;
      if (!name || staticIds.has(`burp:${name}`)) continue;
      entries.push({
        id: `burp:${name}`,
        plugin: MCP_BURP_PLUGIN,
        tool: name,
        mcp_tool: name,
        description: t.description || `Burp MCP tool ${name}`,
        params: { mcp_tool: name },
        web_safe: isBurpPassiveTool(name),
        destructive: isBurpDestructiveTool(name),
        requires_roe: burpToolRequiresRoe(name),
        enabled: true,
        healthy: !degraded,
        dynamic: true,
      });
    }
  } catch (err) {
    catalog.mcp_status = { burp_enabled: true, error: err.message };
  }

  catalog.entries = entries;
  catalog.mcp_burp_tools = BURP_MCP_TOOLS.map((e) => e.id);
  return catalog;
}

function buildFullCatalog(hubPayload) {
  const hubPlugins = (hubPayload?.plugins || []).map(hubPluginToEntry).filter(Boolean);
  const base = {
    fetched_at: new Date().toISOString(),
    hub_status: hubPayload?.status || "unknown",
    hub_plugins: hubPlugins,
    analyzer_profiles: ANALYZER_SCAN_PROFILES,
    knowledge_engine: KNOWLEDGE_ENGINE_TOOLS,
    hub_operations: Object.keys(HUB_OPERATION_ALIASES),
    entries: [
      ...hubPlugins,
      ...NUCLEI_TOOLS,
      ...FFUF_TOOLS,
      ...SQLMAP_TOOLS,
      ...METASPLOIT_TOOLS,
      ...ANALYZER_SCAN_PROFILES,
      ...KNOWLEDGE_ENGINE_TOOLS,
      ...(MCP_BURP_ENABLED() ? BURP_MCP_TOOLS : []),
    ],
  };
  return base;
}

async function fetchHubToolCatalog(integrationHubUrl, axios, authHeaders = {}) {
  const now = Date.now();
  if (cache.catalog && now - cache.fetchedAt < CATALOG_CACHE_TTL_MS) {
    return cache.catalog;
  }

  const base = String(integrationHubUrl || "").replace(/\/$/, "");
  if (!base || !axios) {
    const fallback = await mergeMcpBurpTools(
      buildFullCatalog({ plugins: [], status: "unconfigured" })
    );
    cache.catalog = fallback;
    cache.fetchedAt = now;
    return fallback;
  }

  try {
    const { data } = await axios.get(`${base}/integrations`, {
      timeout: 15000,
      headers: authHeaders,
    });
    const catalog = await mergeMcpBurpTools(buildFullCatalog(data));
    cache.catalog = catalog;
    cache.fetchedAt = now;
    return catalog;
  } catch (err) {
    const fallback = await mergeMcpBurpTools(
      buildFullCatalog({
        plugins: [],
        status: "degraded",
        error: err.message,
      })
    );
    cache.catalog = fallback;
    cache.fetchedAt = now;
    return fallback;
  }
}

function clearToolCatalogCache() {
  cache.catalog = null;
  cache.fetchedAt = 0;
}

function findCatalogEntry(catalog, call) {
  if (!call || !catalog) return null;
  const plugin = String(call.plugin || call.plugin_name || "").toLowerCase();
  const tool = String(call.tool || "").toLowerCase();
  const id = call.id ? String(call.id) : null;

  if (id) {
    const byId = catalog.entries.find((e) => e.id === id);
    if (byId) return byId;
  }

  return catalog.entries.find((e) => {
    const ep = String(e.plugin || "").toLowerCase();
    const et = String(e.tool || "").toLowerCase();
    if (plugin && ep === plugin) return true;
    if (tool && (et === tool || ep === tool)) return true;
    return false;
  });
}

function validateToolCall(call, catalog) {
  const errors = [];
  if (!call || typeof call !== "object") {
    return { valid: false, errors: ["tool call must be an object"] };
  }

  const plugin = call.plugin || call.plugin_name;
  const operation = call.operation || call.hub_operation;
  if (!plugin && !operation) {
    errors.push("plugin or operation is required");
  }

  const entry = findCatalogEntry(catalog, call);
  if (!entry && plugin && !HUB_OPERATION_ALIASES[operation]) {
    errors.push(`unknown plugin/tool: ${plugin || call.tool}`);
  }

  if (entry && entry.enabled === false) {
    errors.push(`plugin disabled: ${entry.plugin}`);
  }

  if (entry && entry.healthy === false) {
    errors.push(`plugin unhealthy: ${entry.plugin}`);
  }

  const params = call.params || call.parameters || call.hub_parameters;
  if (params != null && typeof params !== "object") {
    errors.push("params must be an object");
  }

  return {
    valid: errors.length === 0,
    errors,
    entry: entry || null,
    normalized: normalizeToolCall(call, entry),
  };
}

function normalizeToolCall(call, entry) {
  const plugin =
    call.plugin ||
    call.plugin_name ||
    entry?.plugin ||
    HUB_OPERATION_ALIASES[call.operation || call.hub_operation]?.plugin;
  const params = {
    ...(entry?.params || {}),
    ...(HUB_OPERATION_ALIASES[call.operation || call.hub_operation]?.params || {}),
    ...(call.params || call.parameters || call.hub_parameters || {}),
  };
  if (plugin === MCP_BURP_PLUGIN) {
    const rawTool = call.tool || entry?.tool || params.mcp_tool;
    params.mcp_tool = resolveBurpMcpToolName(rawTool);
    params.mcp_server = params.mcp_server || entry?.mcp_server || "burp";
  }
  return {
    id: call.id || entry?.id,
    tool: call.tool || entry?.tool || plugin,
    plugin,
    params,
    operation: call.operation || call.hub_operation || null,
    rationale: call.rationale || call.reason || null,
  };
}

function filterToolCallsByPolicy(calls, gates = {}) {
  const list = Array.isArray(calls) ? calls : [];
  const engagementPaused = Boolean(
    gates.engagementPaused ?? gates.roeBlocked
  );

  if (!engagementPaused) {
    return { allowed: list, blocked: [] };
  }

  return {
    allowed: [],
    blocked: list.map((call) => ({
      call,
      reason: "Engagement paused",
    })),
  };
}

function parseToolCallsFromContent(content) {
  if (!content) return [];
  if (Array.isArray(content)) return content;
  if (typeof content === "object") {
    return content.tool_calls || content.tools_to_invoke || [];
  }

  const text = String(content);
  try {
    const block = text.match(/\{[\s\S]*\}/);
    if (block) {
      const data = JSON.parse(block[0]);
      return data.tool_calls || data.tools_to_invoke || [];
    }
  } catch {
    /* fall through */
  }
  return [];
}

function formatCatalogForPrompt(catalog, opts = {}) {
  const { webOnly = true, aggressionLevel = 5, maxEntries = 24 } = opts;
  if (!catalog) return "(tool catalog unavailable)";

  const lines = [
    "Available external tools (invoke via tools_to_invoke: [{ tool, plugin, params }]):",
  ];

  const entries = (catalog.entries || []).filter((e) => {
    if (webOnly && e.destructive) return false;
    if (webOnly && !e.web_safe && e.destructive !== false) return false;
    return e.enabled !== false;
  });

  entries.slice(0, maxEntries).forEach((e) => {
    const caps = (e.capabilities || []).slice(0, 4).join(", ");
    lines.push(
      `- ${e.id}: plugin=${e.plugin} tool=${e.tool} — ${e.description}` +
        (caps ? ` [${caps}]` : "")
    );
  });

  lines.push(
    `Hub legacy operations (hub_operation): ${(catalog.hub_operations || []).join(", ")}`,
    `Policy: web_only=${webOnly}, aggression=${aggressionLevel}/10. ` +
      (ALLOW_HIGH_RISK
        ? "ALLOW_HIGH_RISK=true — high-risk tools not blocked by OpSec/council gates."
        : "Do not invoke destructive/exploit tools when web_only unless foothold confirmed.")
  );

  return lines.join("\n");
}

function catalogSummaryForGrounding(catalog) {
  if (!catalog) return { count: 0, plugins: [] };
  return {
    count: catalog.entries?.length || 0,
    hub_status: catalog.hub_status,
    plugins: (catalog.hub_plugins || []).map((p) => ({
      plugin: p.plugin,
      description: p.description,
      capabilities: (p.capabilities || []).slice(0, 6),
      healthy: p.healthy,
    })),
    analyzer_profiles: (catalog.analyzer_profiles || []).map((p) => p.id),
    knowledge_engine: (catalog.knowledge_engine || []).map((p) => p.id),
  };
}

/**
 * Phase-default external tool calls when the AI plan omits tools_to_invoke.
 * Probe phases → scanner plugins; evaluate (phase 4) → KE MITRE chains; commit handled via hub/chain flags.
 */
function defaultToolsForPhase(phaseNum, target, opts = {}) {
  const { webOnly = true, aggressionLevel = 5 } = opts;
  const aggression = Number(aggressionLevel) || 5;
  const maxCalls = aggression >= 7 ? 4 : aggression <= 4 ? 2 : 3;
  const t = String(target || "").toLowerCase();
  const isWeb = webOnly || t.includes("http");
  const calls = [];

  if (phaseNum === 2) {
    calls.push({
      plugin: "nuclei",
      tool: "scan_target",
      params: { operation: "scan_target", severity: "medium,high,critical" },
      rationale: "Auto probe: nuclei scan after recon",
    });
    if (isWeb) {
      calls.push({
        plugin: "ffuf",
        tool: "fuzz_url",
        params: { operation: "fuzz_url" },
        rationale: "Auto probe: ffuf directory fuzz",
      });
    }
  }

  if (phaseNum === 3) {
    calls.push({
      plugin: "nuclei",
      tool: "scan_target",
      params: { operation: "scan_target", severity: "critical,high,medium" },
      rationale: "Auto probe: nuclei vulnerability templates",
    });
    if (isWeb) {
      calls.push({
        plugin: "ffuf",
        tool: "fuzz_vhost",
        params: { operation: "fuzz_vhost" },
        rationale: "Auto probe: ffuf vhost discovery",
      });
    }
  }

  if (phaseNum === 4) {
    calls.push({
      plugin: "knowledge_engine",
      tool: "attack-vector",
      params: { top_chains: aggression >= 7 ? 3 : 2 },
      rationale: "Auto evaluate: MITRE-aligned attack chains via Knowledge Engine",
    });
    if (isWeb && aggression >= 7) {
      calls.push({
        plugin: "sqlmap",
        tool: "test_url",
        params: { operation: "test_url", level: 1, risk: 1 },
        rationale: "Auto evaluate: sqlmap injection test (high aggression)",
      });
    }
  }

  if (aggression <= 4) {
    return calls.filter((c) => c.plugin !== "sqlmap").slice(0, maxCalls);
  }
  return calls.slice(0, maxCalls);
}

function buildRunSummary(eng, ctx) {
  const ga = eng?.guided_autonomous || {};
  const phases = ga.phases || ctx?.phaseRecords || [];
  const completed = phases.filter(
    (p) => p.status === "complete" || p.status === "skipped"
  ).length;
  const toolsUsed = new Set();
  for (const p of phases) {
    for (const tr of p.tool_results || []) {
      if (tr.plugin) toolsUsed.add(tr.plugin);
    }
    for (const hr of p.hub_results || []) {
      if (hr.operation) toolsUsed.add(`hub:${hr.operation}`);
    }
  }
  const pathwayAttempts = (eng?.influence_attempts || []).length;
  const councilTurns = eng?.live_council?.turn ?? 0;
  const councilApprovals = (eng?.live_council?.directives || []).filter(
    (d) => d.approved_at || d.status === "approved"
  ).length;

  return {
    status: ga.status || eng?.status || "unknown",
    phases_completed: completed,
    phases_total: 8,
    tools_invoked_count: ctx?.toolsInvokedCount ?? 0,
    pathway_attempts_count: pathwayAttempts,
    council_turns: councilTurns,
    council_approvals: councilApprovals,
    tools_used: [...toolsUsed],
    assess_complete: Boolean(ga.assess_complete ?? ctx?.assessComplete),
    chain_executed: Boolean(ga.chain_executed ?? ctx?.chainExecuted),
    completed_at: ga.completed_at || eng?.completed_at || null,
  };
}

module.exports = {
  ANALYZER_SCAN_PROFILES,
  KNOWLEDGE_ENGINE_TOOLS,
  NUCLEI_TOOLS,
  FFUF_TOOLS,
  SQLMAP_TOOLS,
  BURP_MCP_TOOLS,
  MCP_BURP_PLUGIN,
  WEB_SCANNER_PLUGINS,
  SQLMAP_ROE_OPERATIONS,
  METASPLOIT_TOOLS,
  METASPLOIT_DESTRUCTIVE_TOOLS,
  DESTRUCTIVE_PLUGINS,
  DESTRUCTIVE_OPERATIONS,
  WEB_ONLY_BLOCKED_PLUGINS,
  WEB_ONLY_BLOCKED_OPERATIONS,
  fetchHubToolCatalog,
  clearToolCatalogCache,
  buildFullCatalog,
  findCatalogEntry,
  validateToolCall,
  normalizeToolCall,
  filterToolCallsByPolicy,
  parseToolCallsFromContent,
  formatCatalogForPrompt,
  catalogSummaryForGrounding,
  defaultToolsForPhase,
  buildRunSummary,
};
