"use strict";

const {
  validateToolCall,
  normalizeToolCall,
  filterToolCallsByPolicy,
  findCatalogEntry,
  METASPLOIT_DESTRUCTIVE_TOOLS,
  WEB_SCANNER_PLUGINS,
  MCP_BURP_PLUGIN,
} = require("./toolCatalog");
const { callTool: mcpCallTool } = require("./mcpClient");
const { LIVE_REQUIRE_APPROVAL, ALLOW_HIGH_RISK } = require("./live-attack/directive-applier");
const { targetUrl } = require("./toolSelector");
const { isEmptyScannerOutcome } = require("./live-attack/influence-pathways");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildPolicyGates(eng, ctx = {}) {
  const council = eng?.live_council || {};
  const lastDirective = council.last_directive || council.pending_directive;
  const gaRoe = eng?.guided_autonomous?.roe_acknowledged;
  const roeAcknowledged =
    gaRoe !== false && ctx.roeAcknowledged !== false;
  return {
    webOnly: ctx.webOnly !== false && eng?.guided_autonomous?.web_only !== false,
    aggressionLevel: ctx.aggressionLevel ?? eng?.aggression_level ?? 5,
    opsecVeto: ALLOW_HIGH_RISK ? false : Boolean(lastDirective?.opsec_veto),
    engagementPaused:
      eng?.status === "aborted" ||
      eng?.status === "paused" ||
      eng?.status === "stopped",
    roeAcknowledged,
    councilApproved:
      ALLOW_HIGH_RISK ||
      ctx.councilApproved === true ||
      Boolean(lastDirective?.tools_approved) ||
      lastDirective?.action === "continue",
    liveRequireApproval: ALLOW_HIGH_RISK ? false : LIVE_REQUIRE_APPROVAL,
  };
}

const PLUGIN_TERMINAL_PREFIX = {
  metasploit: "[msf]",
  nuclei: "[nuclei]",
  ffuf: "[ffuf]",
  sqlmap: "[sqlmap]",
  mcp_burp: "[burp]",
  mcp: "[mcp]",
};

function terminalPrefixForPlugin(plugin) {
  const key = String(plugin || "").toLowerCase();
  return PLUGIN_TERMINAL_PREFIX[key] || "[tool]";
}

function priorMentionsForms(ctx) {
  const text = String(ctx?.priorFindings || "").toLowerCase();
  return /form|parameter|sqlmap|inject|login|cart|checkout/.test(text);
}

function enrichHubPluginParams(normalized, eng, ctx, gates) {
  const plugin = String(normalized.plugin || "").toLowerCase();
  const hostTarget = eng?.target || "unknown";
  const url = targetUrl(hostTarget);
  const targetClass =
    ctx?.targetClass || eng?.guided_autonomous?.target_class || "web_application";

  if (plugin === "nuclei") {
    const op = normalized.params?.operation || normalized.tool;
    const tags =
      normalized.params?.tags ||
      (targetClass.includes("web") || targetClass === "ecommerce"
        ? "cve,http"
        : "cve");
    return {
      ...normalized.params,
      operation: op,
      target: normalized.params?.target || url,
      tags,
      severity: normalized.params?.severity || "critical,high,medium",
      roe_acknowledged: gates.roeAcknowledged,
      web_only: gates.webOnly,
      council_approved: gates.councilApproved,
    };
  }
  if (plugin === "ffuf") {
    const op = normalized.params?.operation || normalized.tool;
    return {
      ...normalized.params,
      operation: op,
      url: normalized.params?.url || url,
      target: normalized.params?.target || hostTarget,
      roe_acknowledged: gates.roeAcknowledged,
      web_only: gates.webOnly,
      council_approved: gates.councilApproved,
    };
  }
  if (plugin === MCP_BURP_PLUGIN) {
    return {
      ...normalized.params,
      mcp_tool: normalized.params?.mcp_tool || normalized.tool,
      mcp_server: normalized.params?.mcp_server || "burp",
      target: normalized.params?.target || eng?.target,
      roe_acknowledged: gates.roeAcknowledged,
      web_only: gates.webOnly,
      council_approved: gates.councilApproved,
    };
  }
  if (plugin === "sqlmap") {
    if (gates.webOnly && !priorMentionsForms(ctx)) {
      return {
        ...normalized.params,
        operation: normalized.params?.operation || normalized.tool,
        target: normalized.params?.target || url,
        skipped: true,
        skip_reason: "no forms/parameters in prior findings",
      };
    }
    return {
      ...normalized.params,
      operation: normalized.params?.operation || normalized.tool,
      target: normalized.params?.target || url,
      level: normalized.params?.level ?? (gates.aggressionLevel >= 7 ? 2 : 1),
      risk: normalized.params?.risk ?? 1,
      roe_acknowledged: gates.roeAcknowledged,
      web_only: gates.webOnly,
      council_approved: gates.councilApproved,
    };
  }
  if (plugin !== "metasploit") {
    const op = normalized.params?.operation || normalized.tool;
    return {
      ...normalized.params,
      operation: op,
      target: normalized.params?.target || eng?.target,
    };
  }
  const op = normalized.params?.operation || normalized.tool;
  const dryRun =
    normalized.params?.dry_run !== undefined ? normalized.params.dry_run : false;
  return {
    ...normalized.params,
    operation: op,
    target: normalized.params?.target || eng?.target,
    roe_acknowledged: gates.roeAcknowledged,
    web_only: gates.webOnly,
    council_approved: gates.councilApproved,
    dry_run: dryRun,
  };
}

async function executeSingleHubPlugin(deps, engagementId, target, normalized) {
  const { axios, INTEGRATION_HUB_URL, getServiceAuthHeaders } = deps;
  const { data } = await axios.post(
    `${INTEGRATION_HUB_URL}/integrations/execute`,
    {
      plugin_name: normalized.plugin,
      engagement_id: engagementId,
      target,
      parameters: normalized.params,
      timeout: 120,
    },
    { timeout: 130000, headers: getServiceAuthHeaders() }
  );
  return data;
}

async function executeMcpBurpTool(normalized) {
  const serverId = normalized.params?.mcp_server || "burp";
  const toolName = normalized.params?.mcp_tool || normalized.tool;
  const mcpArgs = { ...(normalized.params || {}) };
  delete mcpArgs.mcp_server;
  delete mcpArgs.mcp_tool;
  delete mcpArgs.roe_acknowledged;
  delete mcpArgs.web_only;
  delete mcpArgs.council_approved;
  delete mcpArgs.target;
  delete mcpArgs.operation;

  const result = await mcpCallTool(serverId, toolName, mcpArgs);
  const text = result?.text || JSON.stringify(result?.content || result);
  return {
    success: true,
    output: {
      mcp_server: serverId,
      mcp_tool: toolName,
      result,
      terminal_lines: result?.terminal_lines || [`[burp] ${toolName}: ok`],
      summary: typeof text === "string" ? text.slice(0, 4000) : text,
    },
  };
}

async function executeLegacyHubOperation(deps, engagementId, target, normalized) {
  const { axios, INTEGRATION_HUB_URL, getServiceAuthHeaders } = deps;
  const { data } = await axios.post(
    `${INTEGRATION_HUB_URL}/execute`,
    {
      operation: normalized.operation,
      target,
      context: { engagement_id: engagementId },
      ...normalized.params,
      hub_parameters: normalized.params,
    },
    { timeout: 300000, headers: getServiceAuthHeaders() }
  );
  return data;
}

async function executeCatalogTool(deps, opts) {
  const {
    engagementId,
    eng,
    toolCall,
    catalog,
    ctx,
    broadcastTerminal,
    appendReasoningTrace,
    liveAttack,
  } = opts;

  const gates = buildPolicyGates(eng, ctx);
  const validation = validateToolCall(toolCall, catalog);
  if (!validation.valid) {
    return {
      success: false,
      error: validation.errors.join("; "),
      blocked: true,
    };
  }

  const normalized = validation.normalized;
  const target = eng?.target || "unknown";
  const label = `${normalized.plugin}${normalized.tool ? `/${normalized.tool}` : ""}`;
  const prefix = terminalPrefixForPlugin(normalized.plugin);
  normalized.params = enrichHubPluginParams(normalized, eng, ctx, gates);
  if (normalized.params?.skipped) {
    return {
      success: false,
      error: normalized.params.skip_reason || "tool skipped by policy",
      plugin: normalized.plugin,
      blocked: true,
    };
  }

  const runExec = async () => {
    if (normalized.plugin === "analyzer") {
      return executeAnalyzerTool(deps, engagementId, eng, normalized, ctx);
    }
    if (normalized.plugin === "knowledge_engine") {
      return executeKnowledgeEngineTool(deps, eng, normalized);
    }
    if (normalized.plugin === MCP_BURP_PLUGIN) {
      return executeMcpBurpTool(normalized);
    }
    if (normalized.operation && !normalized.plugin) {
      return executeLegacyHubOperation(deps, engagementId, target, normalized);
    }
    return executeSingleHubPlugin(deps, engagementId, target, normalized);
  };

  if (broadcastTerminal) {
    broadcastTerminal(
      engagementId,
      `${prefix} invoking ${label} ${JSON.stringify(normalized.params || {}).slice(0, 100)}`,
      "command"
    );
  }

  if (appendReasoningTrace) {
    appendReasoningTrace(eng, {
      source: "tool_executor",
      pattern_step: "probe",
      subtask_id: "probe:2",
      external_tool: true,
      plugin: normalized.plugin,
      tool: normalized.tool,
      rationale: normalized.rationale || `Execute external tool ${label}`,
      params: normalized.params,
    });
  }

  let result;
  try {
    if (liveAttack?.runWithInfluencePathways) {
      liveAttack.initInfluenceState(eng);
      const pathwayResult = await liveAttack.runWithInfluencePathways({
        eng,
        engagementId,
        task_kind: "external_tool",
        task_id: normalized.id || `${normalized.plugin}_${Date.now()}`,
        context: { normalized },
        broadcastTerminal: (id, msg, level) => {
          if (broadcastTerminal) {
            const p = terminalPrefixForPlugin(normalized.plugin);
            broadcastTerminal(id, msg.replace(/^\[pathway\]/, p), level);
          }
        },
        broadcastCouncil: opts.broadcastCouncil,
        executePrimary: runExec,
        executeAlternate: async (pathway) => {
          const alt = {
            ...normalized,
            params: { ...normalized.params, ...(pathway.params || {}) },
          };
          if (alt.plugin === "analyzer") {
            return executeAnalyzerTool(deps, engagementId, eng, alt, ctx);
          }
          return executeSingleHubPlugin(deps, engagementId, target, alt);
        },
        shouldRetryOnEmpty: (result) =>
          isEmptyScannerOutcome(String(normalized.plugin || "").toLowerCase(), result),
        buildAlternates: (primaryResult) => {
          const plugin = String(normalized.plugin || "").toLowerCase();
          if (liveAttack.buildWebScannerAlternatePathways && WEB_SCANNER_PLUGINS?.has?.(plugin)) {
            const alts = liveAttack.buildWebScannerAlternatePathways(
              plugin,
              normalized.params
            );
            if (isEmptyScannerOutcome(plugin, primaryResult) && plugin === "nuclei") {
              return alts.length
                ? alts
                : [
                    {
                      pathway_id: "nuclei_templates_tech",
                      method: "nuclei_templates",
                      label: "nuclei technologies templates",
                      params: {
                        operation: "scan_target",
                        templates: "http/technologies/",
                        target: normalized.params?.target,
                      },
                    },
                  ];
            }
            if (isEmptyScannerOutcome(plugin, primaryResult) && plugin === "ffuf") {
              const vhostAlt = alts.find((a) => a.method === "ffuf_vhost");
              return vhostAlt ? [vhostAlt, ...alts.filter((a) => a !== vhostAlt)] : alts;
            }
            return alts;
          }
          return (
            liveAttack.buildHubAlternatePathways?.(
              normalized.operation || "reconnaissance",
              normalized.params
            ) || []
          );
        },
      });
      result = pathwayResult.result;
      if (!pathwayResult.success && result?.error) {
        throw new Error(result.error);
      }
    } else {
      result = await runExec();
    }
  } catch (err) {
    if (broadcastTerminal) {
      broadcastTerminal(engagementId, `${prefix} ${label} failed: ${err.message}`, "warning");
    }
    if (appendReasoningTrace) {
      appendReasoningTrace(eng, {
        source: "tool_executor",
        pattern_step: "probe",
        subtask_id: "probe:2",
        external_tool: true,
        plugin: normalized.plugin,
        tool: normalized.tool,
        action: "tool_failed",
        note: err.message,
      });
    }
    return { success: false, error: err.message, plugin: normalized.plugin };
  }

  const out = result?.output;
  const terminalLines = Array.isArray(out?.terminal_lines) ? out.terminal_lines : null;
  if (broadcastTerminal && terminalLines?.length) {
    for (const line of terminalLines.slice(0, 20)) {
      broadcastTerminal(engagementId, line, result?.success === false ? "warning" : "output");
    }
  }

  const summary =
    typeof out === "string"
      ? out.slice(0, 1500)
      : JSON.stringify(out || result).slice(0, 1500);

  if (broadcastTerminal) {
    broadcastTerminal(
      engagementId,
      `${prefix} ${label} ${result?.success === false ? "failed" : "ok"}:\n${summary}`,
      result?.success === false ? "warning" : "success"
    );
  }

  if (appendReasoningTrace) {
    appendReasoningTrace(eng, {
      source: "tool_executor",
      pattern_step: "probe",
      subtask_id: "probe:4",
      external_tool: true,
      plugin: normalized.plugin,
      tool: normalized.tool,
      action: result?.success === false ? "tool_failed" : "tool_complete",
      note: summary.slice(0, 400),
    });
  }

  return {
    success: result?.success !== false,
    plugin: normalized.plugin,
    tool: normalized.tool,
    result,
  };
}

async function executeAnalyzerTool(deps, engagementId, eng, normalized, ctx) {
  const { axios, ANALYZER_URL, getServiceAuthHeaders, broadcastTerminal } = deps;
  if (!ANALYZER_URL) {
    return { success: false, error: "Analyzer URL not configured" };
  }

  const scanType = normalized.params?.scan_type || "quick";
  const { data: startData } = await axios.post(
    `${ANALYZER_URL}/scan`,
    {
      target: eng.target,
      aggression_level: ctx?.aggressionLevel ?? eng?.aggression_level ?? 5,
      scan_type: scanType,
      scan_timeout_sec: normalized.params?.scan_timeout_sec ?? 120,
    },
    { timeout: 30000, headers: getServiceAuthHeaders() }
  );

  const sessionId = startData?.id;
  if (!sessionId) {
    return { success: false, error: "No analyzer session id" };
  }

  if (broadcastTerminal) {
    broadcastTerminal(engagementId, `[tool] analyzer session ${sessionId} polling…`, "info");
  }

  const deadline = Date.now() + (normalized.params?.poll_ms ?? 180000);
  while (Date.now() < deadline) {
    await sleep(2500);
    const resp = await axios.get(`${ANALYZER_URL}/sessions/${sessionId}`, {
      headers: getServiceAuthHeaders(),
      timeout: 15000,
    });
    const sess = resp.data;
    if (sess.status === "ready") {
      eng.fingerprint = sess.fingerprint || eng.fingerprint;
      if (ctx) ctx.fingerprint = sess.fingerprint || ctx.fingerprint;
      return { success: true, output: sess, session_id: sessionId };
    }
    if (sess.status === "error") {
      return { success: false, error: sess.error || "analyzer error", output: sess };
    }
  }

  return { success: false, error: "analyzer poll timeout" };
}

async function executeKnowledgeEngineTool(deps, eng, normalized) {
  const { axios, KNOWLEDGE_ENGINE, getServiceAuthHeaders } = deps;
  const tool = String(normalized.tool || "search");
  const path = tool.startsWith("/") ? tool : `/${tool}`;
  const method = path.includes("predict") ? "ml/predict" : path.replace(/^\//, "");

  let body = { ...(normalized.params || {}) };
  if (method === "search") {
    body = {
      query: body.query || eng.target,
      top_k: body.top_k ?? 10,
    };
  } else if (method === "attack-vector") {
    body = {
      target_description: body.target_description || eng.target,
      detected_services: body.detected_services || [],
      top_chains: body.top_chains ?? 3,
    };
  } else if (method === "ml/predict") {
    body = {
      text: body.text || eng.target,
      target: body.target || "category",
      top_k: body.top_k ?? 5,
    };
  }

  const endpoint =
    method === "ml/predict"
      ? `${KNOWLEDGE_ENGINE}/ml/predict`
      : `${KNOWLEDGE_ENGINE}/${method}`;

  const { data } = await axios.post(endpoint, body, {
    timeout: 90000,
    headers: getServiceAuthHeaders(),
  });
  return { success: true, output: data };
}

async function executeToolCalls(deps, opts) {
  const { calls, catalog, engagementId, eng, ctx } = opts;
  if (!Array.isArray(calls) || !calls.length) {
    return { results: [], blocked: [] };
  }

  const gates = buildPolicyGates(eng, ctx);
  const validated = calls.map((c) => {
    const v = validateToolCall(c, catalog);
    return v.valid ? { ...v.normalized, _entry: v.entry || findCatalogEntry(catalog, c) } : null;
  }).filter(Boolean);

  const { allowed } = filterToolCallsByPolicy(validated, gates);
  const results = [];

  for (const call of allowed) {
    const outcome = await executeCatalogTool(deps, {
      ...opts,
      toolCall: call,
    });
    results.push(outcome);
    await sleep(300);
  }

  return { results, blocked: [] };
}

module.exports = {
  buildPolicyGates,
  executeCatalogTool,
  executeToolCalls,
};
