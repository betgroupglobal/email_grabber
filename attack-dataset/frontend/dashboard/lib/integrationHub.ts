/** Integration Hub API client (browser → port 8500). */

import { orchestratorAuthHeaders, orchestratorHttp } from "@/lib/config";

export const INTEGRATION_HUB_URL =
  process.env.NEXT_PUBLIC_INTEGRATION_HUB_URL || "http://localhost:8500";

export function integrationHubHttp(path: string): string {
  const base = INTEGRATION_HUB_URL.replace(/\/$/, "");
  return path.startsWith("/") ? `${base}${path}` : `${base}/${path}`;
}

export type HubPlugin = {
  name: string;
  version?: string;
  description?: string;
  category?: string;
  status?: string;
  health_status?: string;
  enabled?: boolean;
  healthy?: boolean;
  capabilities?: string[];
  execution_types?: string[];
  opsec_enabled?: boolean;
  last_run?: string | null;
  last_health_check?: string | null;
};

export type HubOperation = {
  id: string;
  type: string;
  status: "running" | "completed" | "failed" | "paused";
  target?: string;
  progress: number;
  started_at: string;
  completed_at?: string;
  error?: string;
};

export type HubMonitoringSession = {
  id: string;
  target: string;
  status: "active" | "paused" | "completed";
  metrics: {
    scans_completed: number;
    vulnerabilities_found: number;
    data_exfiltrated: number;
  };
};

export type HubExecutionRecord = {
  id: string;
  plugin_name: string;
  operation?: string | null;
  target: string;
  success: boolean;
  error?: string | null;
  execution_time?: number | null;
  created_at: string;
};

export type HubHealth = {
  status: string;
  service?: string;
  plugin_count?: number;
  plugins_ready?: number;
  plugins_healthy?: number;
};

export type McpServerStatus = {
  id: string;
  name?: string;
  transport?: string;
  url?: string | null;
  enabled?: boolean;
  connected?: boolean;
};

export type OrchestratorMcpStatus = {
  mock?: boolean;
  burp_enabled?: boolean;
  burp_configured?: boolean;
  servers?: McpServerStatus[];
  mcp_status?: {
    burp_enabled?: boolean;
    tool_count?: number;
    error?: string | null;
    degraded?: boolean;
  };
  timestamp?: string;
  error?: string;
};

export type HubExecuteResult = {
  success: boolean;
  output?: unknown;
  error?: string | null;
  artifacts?: unknown[];
  opsec_context?: Record<string, unknown> | null;
  opsec_assessment?: Record<string, unknown> | null;
  execution_time?: number;
  plugin?: string;
  operation_id?: string;
};

const SESSION_HISTORY_KEY = "integration-hub-execution-history";

export function parseHubError(
  status: number,
  body: Record<string, unknown> | null
): string {
  if (!body) {
    return `Integration Hub error (HTTP ${status})`;
  }
  const detail = body.detail ?? body.error ?? body.message;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((d) =>
        typeof d === "object" && d && "msg" in d
          ? String((d as { msg: string }).msg)
          : String(d)
      )
      .join("; ");
  }
  return `Integration Hub error (HTTP ${status})`;
}

export async function hubFetchJson<T>(
  path: string,
  init?: RequestInit
): Promise<{ ok: boolean; status: number; data: T | null; error: string | null }> {
  try {
    const response = await fetch(integrationHubHttp(path), init);
    const data = (await response.json().catch(() => null)) as T | null;
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        data,
        error: parseHubError(
          response.status,
          (data as Record<string, unknown>) || null
        ),
      };
    }
    return { ok: true, status: response.status, data, error: null };
  } catch {
    return {
      ok: false,
      status: 0,
      data: null,
      error: `Cannot reach Integration Hub at ${INTEGRATION_HUB_URL}`,
    };
  }
}

export function mapPluginFromApi(raw: Record<string, unknown>): HubPlugin {
  const status = String(raw.status || "ready");
  const health = String(raw.health_status || "unknown");
  const caps = raw.capabilities as string[] | undefined;
  const execTypes = raw.execution_types as string[] | undefined;
  return {
    name: String(raw.name || ""),
    version: raw.version as string | undefined,
    description: raw.description as string | undefined,
    category: raw.category as string | undefined,
    status,
    health_status: health,
    enabled: raw.enabled !== undefined ? Boolean(raw.enabled) : status !== "disabled",
    healthy: health === "healthy" || raw.healthy === true,
    capabilities: caps?.length ? caps : execTypes,
    execution_types: execTypes,
    opsec_enabled: Boolean(raw.opsec_enabled),
    last_run: (raw.last_run as string | null) ?? null,
    last_health_check: (raw.last_health_check as string | null) ?? null,
  };
}

export function mapOperationFromApi(raw: Record<string, unknown>): HubOperation {
  const status = String(raw.status || "running").toLowerCase();
  const normalized =
    status === "abort" || status === "stop"
      ? "failed"
      : status === "pause"
        ? "paused"
        : (status as HubOperation["status"]);
  return {
    id: String(raw.operation_id || raw.id || ""),
    type: String(raw.type || raw.operation_type || "automation"),
    status: normalized,
    target: (raw.target as string) || undefined,
    progress: typeof raw.progress === "number" ? raw.progress : 0,
    started_at: String(raw.created_at || raw.started_at || new Date().toISOString()),
    completed_at: raw.completed_at as string | undefined,
    error: raw.error as string | undefined,
  };
}

export function mapMonitoringFromApi(
  raw: Record<string, unknown>
): HubMonitoringSession {
  const targets = raw.targets as string[] | undefined;
  return {
    id: String(raw.session_id || raw.id || ""),
    target: targets?.join(", ") || String(raw.target || "—"),
    status: String(raw.status || "active") as HubMonitoringSession["status"],
    metrics: {
      scans_completed: Number(raw.scans_completed ?? 0),
      vulnerabilities_found: Number(raw.vulnerabilities_found ?? 0),
      data_exfiltrated: Number(raw.data_exfiltrated ?? 0),
    },
  };
}

export function mapExecutionFromApi(
  raw: Record<string, unknown>
): HubExecutionRecord {
  return {
    id: String(raw.id || ""),
    plugin_name: String(raw.plugin_name || ""),
    operation: (raw.operation as string) || null,
    target: String(raw.target || "—"),
    success: Boolean(raw.success),
    error: (raw.error as string) || null,
    execution_time:
      typeof raw.execution_time === "number" ? raw.execution_time : null,
    created_at: String(raw.created_at || new Date().toISOString()),
  };
}

export function loadSessionExecutionHistory(): HubExecutionRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(SESSION_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HubExecutionRecord[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveSessionExecutionHistory(records: HubExecutionRecord[]): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(
      SESSION_HISTORY_KEY,
      JSON.stringify(records.slice(0, 50))
    );
  } catch {
    /* ignore quota */
  }
}

export function appendSessionExecution(record: HubExecutionRecord): void {
  const prev = loadSessionExecutionHistory();
  saveSessionExecutionHistory([record, ...prev.filter((r) => r.id !== record.id)]);
}

export async function fetchOrchestratorMcpStatus(): Promise<{
  status: OrchestratorMcpStatus | null;
  error: string | null;
}> {
  try {
    const res = await fetch(orchestratorHttp("/mcp/status"), {
      headers: { ...orchestratorAuthHeaders() },
    });
    if (!res.ok) {
      return {
        status: null,
        error: `Orchestrator MCP status (HTTP ${res.status})`,
      };
    }
    const data = (await res.json()) as OrchestratorMcpStatus;
    return { status: data, error: null };
  } catch (e) {
    return {
      status: null,
      error: e instanceof Error ? e.message : "Cannot reach orchestrator MCP status",
    };
  }
}

export async function fetchHubHealth(): Promise<{
  health: HubHealth | null;
  error: string | null;
}> {
  const res = await hubFetchJson<HubHealth>("/health");
  return { health: res.data, error: res.error };
}

export async function fetchHubPlugins(refreshHealth = true): Promise<{
  plugins: HubPlugin[];
  error: string | null;
}> {
  const q = refreshHealth ? "?refresh_health=true" : "";
  const res = await hubFetchJson<{ plugins?: Record<string, unknown>[] }>(
    `/api/v1/plugins${q}`
  );
  if (!res.ok || !res.data) {
    return { plugins: [], error: res.error };
  }
  return {
    plugins: (res.data.plugins || []).map((p) => mapPluginFromApi(p)),
    error: null,
  };
}

export async function fetchHubExecutions(limit = 30): Promise<{
  executions: HubExecutionRecord[];
  error: string | null;
}> {
  const res = await hubFetchJson<{ executions?: Record<string, unknown>[] }>(
    `/api/v1/executions?limit=${limit}`
  );
  if (!res.ok || !res.data) {
    return { executions: [], error: res.error };
  }
  return {
    executions: (res.data.executions || []).map((e) => mapExecutionFromApi(e)),
    error: null,
  };
}

export async function executeHubPlugin(payload: {
  plugin_name: string;
  target: string;
  engagement_id?: string;
  parameters: Record<string, unknown>;
  timeout?: number;
  run_opsec_assessment?: boolean;
}): Promise<{ result: HubExecuteResult | null; error: string | null }> {
  const res = await hubFetchJson<HubExecuteResult>("/integrations/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      engagement_id: payload.engagement_id || "dashboard",
      target: payload.target,
      plugin_name: payload.plugin_name,
      parameters: payload.parameters,
      timeout: payload.timeout ?? 120,
      run_opsec_assessment: payload.run_opsec_assessment ?? false,
      metadata: payload.run_opsec_assessment
        ? { run_opsec_assessment: true }
        : {},
    }),
  });
  if (!res.ok) {
    return { result: res.data, error: res.error };
  }
  return { result: res.data, error: null };
}

export function operationsForPlugin(plugin: HubPlugin): string[] {
  if (plugin.capabilities?.length) {
    return plugin.capabilities;
  }
  if (plugin.name === "metasploit") {
    return [
      "list_modules",
      "run_auxiliary",
      "run_exploit",
      "generate_payload",
    ];
  }
  if (plugin.name === "mcp_burp") {
    return ["list_mcp_tools", "call_mcp_tool", "list_servers"];
  }
  if (plugin.name === "nmap") {
    return ["tcp", "udp", "syn", "connect"];
  }
  if (plugin.name === "virustotal") {
    return ["url", "ip", "domain", "file"];
  }
  return ["default"];
}

export function defaultParametersFor(
  pluginName: string,
  operation: string,
  target: string
): Record<string, unknown> {
  if (pluginName === "jailbreak_ai") {
    return {
      operation,
      messages: [
        {
          role: "user",
          content: `Authorized pentest task (${operation}) for target ${target || "unspecified"}.`,
        },
      ],
      target_info: { target },
    };
  }
  if (pluginName === "metasploit") {
    return {
      operation: operation === "default" ? "list_modules" : operation,
      target,
      dry_run: false,
      roe_acknowledged: true,
      web_only: true,
      ...(operation === "run_auxiliary"
        ? { module: "auxiliary/scanner/http/http_version" }
        : {}),
    };
  }
  if (pluginName === "nmap") {
    return { target, scan_type: operation === "default" ? "tcp" : operation };
  }
  if (pluginName === "mcp_burp") {
    return {
      operation: operation === "default" ? "list_mcp_tools" : operation,
      mcp_server: "burp",
      ...(operation === "call_mcp_tool"
        ? { mcp_tool: "get_proxy_http_history", arguments: { count: 5, offset: 0 } }
        : {}),
    };
  }
  if (pluginName === "nuclei") {
    return {
      target,
      operation: operation === "default" ? "scan_target" : operation,
      severity: "medium,high,critical",
    };
  }
  if (pluginName === "ffuf") {
    return {
      target,
      operation: operation === "default" ? "fuzz_url" : operation,
    };
  }
  if (pluginName === "sqlmap") {
    return {
      target,
      operation: operation === "default" ? "test_url" : operation,
      level: 1,
      risk: 1,
      roe_acknowledged: true,
    };
  }
  if (pluginName === "metasploit") {
    return {
      target,
      operation: operation === "default" ? "list_modules" : operation,
      dry_run: false,
      roe_acknowledged: true,
    };
  }
  if (pluginName === "virustotal") {
    return { resource: target, scan_type: operation === "default" ? "auto" : operation };
  }
  return { target, operation };
}
