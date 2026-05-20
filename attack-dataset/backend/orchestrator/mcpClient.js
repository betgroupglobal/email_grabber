"use strict";

const { spawn } = require("child_process");
const { resolveBurpMcpToolName } = require("./mcpBurpTools");

const TRUTHY = new Set(["1", "true", "yes"]);

const MCP_MOCK = () => TRUTHY.has(String(process.env.MCP_MOCK || "").toLowerCase());

const MCP_BURP_ENABLED = () => {
  if (MCP_MOCK()) return true;
  return TRUTHY.has(String(process.env.MCP_BURP_ENABLED || "").toLowerCase());
};

/** @type {Map<string, object>} */
const serverRegistry = new Map();
/** @type {Map<string, { tools: object[], fetchedAt: number }>} */
const toolsCache = new Map();
const TOOLS_CACHE_MS = Math.max(
  5000,
  parseInt(process.env.MCP_TOOLS_CACHE_MS || "120000", 10)
);

const MOCK_BURP_TOOLS = [
  { name: "send_http1_request", description: "Issues an HTTP/1.1 request and returns the response." },
  { name: "send_http2_request", description: "Issues an HTTP/2 request and returns the response." },
  { name: "get_proxy_http_history", description: "Displays items within the proxy HTTP history" },
  { name: "get_proxy_http_history_regex", description: "Proxy HTTP history matching regex" },
  { name: "get_scanner_issues", description: "Scanner issues identified by Burp" },
  { name: "create_repeater_tab", description: "Creates a new Repeater tab" },
  { name: "send_to_intruder", description: "Sends request to Intruder" },
  { name: "set_proxy_intercept_state", description: "Enable or disable Proxy Intercept" },
  { name: "output_project_options", description: "Export project-level configuration JSON" },
];

function parseCommandLine(cmdLine) {
  const parts = String(cmdLine || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return null;
  return { command: parts[0], args: parts.slice(1) };
}

function parseMcpServersJson() {
  const raw = process.env.MCP_SERVERS_JSON;
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function loadServerRegistry() {
  serverRegistry.clear();

  if (MCP_BURP_ENABLED()) {
    const burp = {
      id: "burp",
      name: "PortSwigger Burp MCP",
      transport: process.env.MCP_BURP_COMMAND ? "stdio" : "sse",
      url: process.env.MCP_BURP_URL || "http://127.0.0.1:9876",
      command: process.env.MCP_BURP_COMMAND || null,
      commandArgs: process.env.MCP_BURP_ARGS
        ? process.env.MCP_BURP_ARGS.split(/\s+/).filter(Boolean)
        : [],
      token: process.env.MCP_BURP_TOKEN || null,
      enabled: true,
    };
    if (burp.command) {
      const parsed = parseCommandLine(burp.command);
      if (parsed) {
        burp.spawnCommand = parsed.command;
        burp.spawnArgs = [...parsed.args, ...burp.commandArgs];
      }
    } else if (!burp.url) {
      burp.transport = "mock";
    }
    if (MCP_MOCK()) burp.transport = "mock";
    serverRegistry.set("burp", burp);
  }

  for (const entry of parseMcpServersJson()) {
    const id = entry.id || entry.name;
    if (!id) continue;
    serverRegistry.set(String(id), {
      id: String(id),
      name: entry.name || id,
      transport: entry.transport || (entry.command ? "stdio" : "sse"),
      url: entry.url || null,
      command: entry.command || null,
      commandArgs: entry.args || entry.commandArgs || [],
      token: entry.token || null,
      enabled: entry.enabled !== false,
    });
  }

  return serverRegistry;
}

function getMcpStatus() {
  loadServerRegistry();
  const servers = [];
  for (const [id, cfg] of serverRegistry) {
    servers.push({
      id,
      name: cfg.name,
      transport: cfg.transport,
      url: cfg.url || null,
      enabled: cfg.enabled,
      connected: MCP_MOCK() || cfg.transport === "mock",
    });
  }
  return {
    mock: MCP_MOCK(),
    burp_enabled: MCP_BURP_ENABLED(),
    servers,
    burp_configured: MCP_BURP_ENABLED() && serverRegistry.has("burp"),
  };
}

function mockCallTool(serverId, toolName, args) {
  const resolved = serverId === "burp" ? resolveBurpMcpToolName(toolName) : toolName;
  const payload = {
    mock: true,
    server_id: serverId,
    tool: resolved,
    arguments: args || {},
    content: [
      {
        type: "text",
        text: `[MCP mock] ${resolved} executed successfully`,
      },
    ],
    terminal_lines: [`[burp] mock ${resolved}: ok`],
  };

  if (resolved === "get_proxy_http_history" || resolved === "get_proxy_history") {
    payload.content[0].text = JSON.stringify(
      [
        {
          method: "GET",
          url: "https://example.com/",
          status: 200,
          note: "mock proxy history entry",
        },
      ],
      null,
      2
    );
  } else if (resolved === "get_scanner_issues" || resolved === "run_scan") {
    payload.content[0].text = JSON.stringify(
      [{ name: "Mock finding", severity: "info", detail: "MCP_MOCK=1" }],
      null,
      2
    );
  } else if (resolved.startsWith("send_http")) {
    payload.content[0].text = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nmock response body";
  }

  return payload;
}

class McpStdioSession {
  constructor(serverId, cfg) {
    this.serverId = serverId;
    this.cfg = cfg;
    this.proc = null;
    this.nextId = 1;
    this.pending = new Map();
    this.buffer = "";
    this.ready = null;
    this.readyResolve = null;
    this.readyReject = null;
    this.ready = new Promise((resolve, reject) => {
      this.readyResolve = resolve;
      this.readyReject = reject;
    });
  }

  start() {
    const cmd = this.cfg.spawnCommand || this.cfg.command;
    const args = this.cfg.spawnArgs?.length
      ? this.cfg.spawnArgs
      : this.cfg.commandArgs || [];
    if (!cmd) {
      this.readyReject(new Error("MCP stdio command not configured"));
      return;
    }

    this.proc = spawn(cmd, args, {
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env },
    });

    this.proc.stdout.on("data", (chunk) => this._onData(chunk));
    this.proc.stderr.on("data", (chunk) => {
      const line = chunk.toString().trim();
      if (line) process.stderr.write(`[mcp:${this.serverId}] ${line}\n`);
    });
    this.proc.on("error", (err) => this.readyReject(err));
    this.proc.on("exit", (code) => {
      for (const [, { reject }] of this.pending) {
        reject(new Error(`MCP stdio exited (${code})`));
      }
      this.pending.clear();
    });

    this._request("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "opsecai-orchestrator", version: "1.0.0" },
    })
      .then(() => {
        this._notify("notifications/initialized", {});
        return this.readyResolve(true);
      })
      .catch((err) => this.readyReject(err));
  }

  _onData(chunk) {
    this.buffer += chunk.toString();
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const msg = JSON.parse(trimmed);
        if (msg.id != null && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
          else resolve(msg.result);
        }
      } catch {
        /* ignore non-json */
      }
    }
  }

  _notify(method, params) {
    const payload = JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n";
    this.proc.stdin.write(payload);
  }

  _request(method, params) {
    const id = this.nextId++;
    const payload =
      JSON.stringify({ jsonrpc: "2.0", id, method, params: params || {} }) + "\n";
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.proc.stdin.write(payload, (err) => {
        if (err) reject(err);
      });
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`MCP request timeout: ${method}`));
        }
      }, parseInt(process.env.MCP_REQUEST_TIMEOUT_MS || "60000", 10));
    });
  }

  async listTools() {
    await this.ready;
    const result = await this._request("tools/list", {});
    return result?.tools || [];
  }

  async callTool(name, args) {
    await this.ready;
    const result = await this._request("tools/call", { name, arguments: args || {} });
    return result;
  }
}

/** @type {Map<string, McpStdioSession>} */
const stdioSessions = new Map();

async function getStdioSession(serverId, cfg) {
  if (!stdioSessions.has(serverId)) {
    const session = new McpStdioSession(serverId, cfg);
    session.start();
    stdioSessions.set(serverId, session);
  }
  return stdioSessions.get(serverId);
}

async function listToolsSse(cfg) {
  const base = String(cfg.url || "").replace(/\/$/, "");
  const url = base.endsWith("/sse") ? base : `${base}/sse`;
  const headers = { Accept: "text/event-stream" };
  if (cfg.token) headers.Authorization = `Bearer ${cfg.token}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const resp = await fetch(url, { headers, signal: controller.signal });
    clearTimeout(timeout);
    if (!resp.ok) {
      throw new Error(`Burp MCP SSE unreachable (${resp.status})`);
    }
    return MOCK_BURP_TOOLS;
  } catch (err) {
    throw new Error(`Burp MCP SSE connect failed: ${err.message}`);
  }
}

async function callToolSse(cfg, toolName, args) {
  const base = String(cfg.url || "").replace(/\/$/, "");
  const postUrl = `${base}/message`;
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  if (cfg.token) headers.Authorization = `Bearer ${cfg.token}`;

  const body = {
    jsonrpc: "2.0",
    id: Date.now(),
    method: "tools/call",
    params: { name: toolName, arguments: args || {} },
  };

  const resp = await fetch(postUrl, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`MCP tools/call failed (${resp.status}): ${text.slice(0, 200)}`);
  }
  const data = await resp.json();
  if (data.error) throw new Error(data.error.message || JSON.stringify(data.error));
  return data.result;
}

async function listTools(serverId) {
  loadServerRegistry();
  const cfg = serverRegistry.get(serverId);
  if (!cfg || cfg.enabled === false) {
    return { tools: [], error: `unknown or disabled MCP server: ${serverId}` };
  }

  const cached = toolsCache.get(serverId);
  if (cached && Date.now() - cached.fetchedAt < TOOLS_CACHE_MS) {
    return { tools: cached.tools };
  }

  if (MCP_MOCK() || cfg.transport === "mock") {
    const tools = serverId === "burp" ? MOCK_BURP_TOOLS : [];
    toolsCache.set(serverId, { tools, fetchedAt: Date.now() });
    return { tools };
  }

  try {
    let tools = [];
    if (cfg.transport === "stdio") {
      const session = await getStdioSession(serverId, cfg);
      tools = await session.listTools();
    } else if (cfg.transport === "sse") {
      tools = await listToolsSse(cfg);
    }
    toolsCache.set(serverId, { tools, fetchedAt: Date.now() });
    return { tools };
  } catch (err) {
    if (serverId === "burp") {
      const fallback = MOCK_BURP_TOOLS.map((t) => ({ ...t, degraded: true }));
      return { tools: fallback, error: err.message, degraded: true };
    }
    return { tools: [], error: err.message };
  }
}

async function callTool(serverId, toolName, args = {}) {
  loadServerRegistry();
  const cfg = serverRegistry.get(serverId);
  if (!cfg || cfg.enabled === false) {
    throw new Error(`unknown or disabled MCP server: ${serverId}`);
  }

  const name =
    serverId === "burp" ? resolveBurpMcpToolName(toolName) : String(toolName);

  if (MCP_MOCK() || cfg.transport === "mock") {
    const mock = mockCallTool(serverId, name, args);
    const text =
      mock.content?.map((c) => c.text).join("\n") || JSON.stringify(mock);
    return { ...mock, text };
  }

  try {
    let result;
    if (cfg.transport === "stdio") {
      const session = await getStdioSession(serverId, cfg);
      result = await session.callTool(name, args);
    } else if (cfg.transport === "sse") {
      result = await callToolSse(cfg, name, args);
    } else {
      throw new Error(`unsupported MCP transport: ${cfg.transport}`);
    }

    const text =
      result?.content
        ?.filter((c) => c.type === "text")
        .map((c) => c.text)
        .join("\n") || JSON.stringify(result);

    return {
      ...result,
      terminal_lines: [`[burp] ${name}: ok`],
      text,
    };
  } catch (err) {
    if (MCP_MOCK()) return mockCallTool(serverId, name, args);
    throw err;
  }
}

function clearMcpToolsCache() {
  toolsCache.clear();
}

function listServers() {
  loadServerRegistry();
  return Array.from(serverRegistry.values()).map((s) => ({
    id: s.id,
    name: s.name,
    transport: s.transport,
    url: s.url,
    enabled: s.enabled,
  }));
}

module.exports = {
  MCP_MOCK,
  MCP_BURP_ENABLED,
  loadServerRegistry,
  getMcpStatus,
  listServers,
  listTools,
  callTool,
  clearMcpToolsCache,
  mockCallTool,
};
