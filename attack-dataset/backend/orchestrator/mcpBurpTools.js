"use strict";

/**
 * Static Burp MCP tool catalog entries (PortSwigger mcp-server + aliases).
 * Dynamic tools from listTools() are merged in toolCatalog when MCP is enabled.
 */

/** MCP tool name → catalog alias id */
const BURP_TOOL_ALIASES = {
  send_request: "send_http1_request",
  get_proxy_history: "get_proxy_http_history",
  run_scan: "get_scanner_issues",
  site_map: "get_scanner_issues",
};

/** Passive / read-only tools allowed under web_only */
const BURP_PASSIVE_TOOLS = new Set([
  "get_proxy_http_history",
  "get_proxy_http_history_regex",
  "get_proxy_websocket_history",
  "get_proxy_websocket_history_regex",
  "get_scanner_issues",
  "output_project_options",
  "output_user_options",
  "get_active_editor_contents",
  "get_collaborator_interactions",
  "url_encode",
  "url_decode",
  "base64_encode",
  "base64_decode",
  "generate_random_string",
]);

/** Active HTTP / workflow tools — require roe_acknowledged */
const BURP_ACTIVE_TOOLS = new Set([
  "send_http1_request",
  "send_http2_request",
  "create_repeater_tab",
  "send_to_intruder",
  "set_proxy_intercept_state",
  "set_task_execution_engine_state",
  "generate_collaborator_payload",
]);

/** Config mutation — destructive, aggression + ROE */
const BURP_DESTRUCTIVE_TOOLS = new Set([
  "set_project_options",
  "set_user_options",
  "set_active_editor_contents",
]);

const BURP_TOOL_SPECS = [
  {
    mcpTool: "send_http1_request",
    description: "Issue HTTP/1.1 request via Burp and return response",
    destructive: false,
    requires_roe: true,
  },
  {
    mcpTool: "send_http2_request",
    description: "Issue HTTP/2 request via Burp and return response",
    destructive: false,
    requires_roe: true,
  },
  {
    mcpTool: "get_proxy_http_history",
    description: "Paginated proxy HTTP history from Burp",
    destructive: false,
    requires_roe: false,
  },
  {
    mcpTool: "get_proxy_http_history_regex",
    description: "Proxy HTTP history filtered by regex",
    destructive: false,
    requires_roe: false,
  },
  {
    mcpTool: "get_scanner_issues",
    description: "Burp Scanner issues (Professional edition)",
    destructive: false,
    requires_roe: false,
  },
  {
    mcpTool: "create_repeater_tab",
    description: "Open Repeater tab with raw HTTP request",
    destructive: false,
    requires_roe: true,
  },
  {
    mcpTool: "send_to_intruder",
    description: "Send request to Burp Intruder",
    destructive: false,
    requires_roe: true,
  },
  {
    mcpTool: "set_proxy_intercept_state",
    description: "Enable or disable Burp Proxy intercept",
    destructive: false,
    requires_roe: true,
  },
  {
    mcpTool: "output_project_options",
    description: "Export Burp project options JSON schema",
    destructive: false,
    requires_roe: false,
  },
  {
    mcpTool: "generate_collaborator_payload",
    description: "Generate Burp Collaborator OOB payload (Pro)",
    destructive: false,
    requires_roe: true,
  },
];

function burpCatalogEntry(spec) {
  const tool = spec.mcpTool;
  const passive = BURP_PASSIVE_TOOLS.has(tool);
  const active = BURP_ACTIVE_TOOLS.has(tool);
  const destructive = BURP_DESTRUCTIVE_TOOLS.has(tool) || spec.destructive;
  return {
    id: `burp:${tool}`,
    plugin: "mcp_burp",
    tool,
    mcp_tool: tool,
    mcp_server: "burp",
    description: spec.description,
    params: { mcp_tool: tool },
    web_safe: passive && !destructive,
    destructive,
    requires_roe: spec.requires_roe ?? active,
    enabled: true,
    healthy: true,
  };
}

function buildBurpStaticCatalogEntries() {
  const entries = BURP_TOOL_SPECS.map(burpCatalogEntry);
  for (const [alias, target] of Object.entries(BURP_TOOL_ALIASES)) {
    const base = entries.find((e) => e.tool === target);
    if (!base) continue;
    entries.push({
      ...base,
      id: `burp:${alias}`,
      tool: alias,
      mcp_tool: target,
      description: `${base.description} (alias → ${target})`,
    });
  }
  return entries;
}

function resolveBurpMcpToolName(toolOrAlias) {
  const t = String(toolOrAlias || "").toLowerCase();
  return BURP_TOOL_ALIASES[t] || t;
}

function isBurpPassiveTool(toolName) {
  return BURP_PASSIVE_TOOLS.has(resolveBurpMcpToolName(toolName));
}

function isBurpDestructiveTool(toolName) {
  const resolved = resolveBurpMcpToolName(toolName);
  return BURP_DESTRUCTIVE_TOOLS.has(resolved);
}

function burpToolRequiresRoe(toolName) {
  const resolved = resolveBurpMcpToolName(toolName);
  if (BURP_PASSIVE_TOOLS.has(resolved)) return false;
  if (BURP_ACTIVE_TOOLS.has(resolved) || BURP_DESTRUCTIVE_TOOLS.has(resolved)) {
    return true;
  }
  const spec = BURP_TOOL_SPECS.find((s) => s.mcpTool === resolved);
  return Boolean(spec?.requires_roe);
}

module.exports = {
  BURP_TOOL_ALIASES,
  BURP_PASSIVE_TOOLS,
  BURP_ACTIVE_TOOLS,
  BURP_DESTRUCTIVE_TOOLS,
  BURP_TOOL_SPECS,
  buildBurpStaticCatalogEntries,
  resolveBurpMcpToolName,
  isBurpPassiveTool,
  isBurpDestructiveTool,
  burpToolRequiresRoe,
};
