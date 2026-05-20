"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  integrationHubHttp,
  mapOperationFromApi,
  mapMonitoringFromApi,
  mapExecutionFromApi,
  fetchHubHealth,
  fetchHubPlugins,
  fetchHubExecutions,
  fetchOrchestratorMcpStatus,
  loadSessionExecutionHistory,
  type OrchestratorMcpStatus,
  type HubPlugin,
  type HubOperation,
  type HubMonitoringSession,
  type HubExecutionRecord,
  type HubHealth,
} from "@/lib/integrationHub";

/** Offensive tools are invoked via Autonomous Ops (/operations), not manual hub UI. */
const OFFENSIVE_TOOL_PLUGINS = new Set([
  "metasploit",
  "nuclei",
  "ffuf",
  "sqlmap",
  "mcp_burp",
  "nmap",
]);

function formatRelativeTime(iso?: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return "Just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return new Date(iso).toLocaleString();
}

export default function IntegrationHub() {
  const [plugins, setPlugins] = useState<HubPlugin[]>([]);
  const [operations, setOperations] = useState<HubOperation[]>([]);
  const [monitoringSessions, setMonitoringSessions] = useState<HubMonitoringSession[]>([]);
  const [executions, setExecutions] = useState<HubExecutionRecord[]>([]);
  const [hubHealth, setHubHealth] = useState<HubHealth | null>(null);
  const [mcpStatus, setMcpStatus] = useState<OrchestratorMcpStatus | null>(null);
  const [mcpError, setMcpError] = useState<string | null>(null);
  const [hubError, setHubError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [selectedPlugin, setSelectedPlugin] = useState<string | null>(null);
  const [pluginDetails, setPluginDetails] = useState<Record<string, unknown> | null>(null);

  const refreshAll = useCallback(async () => {
    const [healthRes, pluginRes, execRes, mcpRes] = await Promise.all([
      fetchHubHealth(),
      fetchHubPlugins(true),
      fetchHubExecutions(40),
      fetchOrchestratorMcpStatus(),
    ]);

    if (mcpRes.error) {
      setMcpError(mcpRes.error);
      setMcpStatus(null);
    } else {
      setMcpError(null);
      setMcpStatus(mcpRes.status);
    }

    if (healthRes.error) {
      setHubError(healthRes.error);
    } else {
      setHubHealth(healthRes.health);
      if (!pluginRes.error) setHubError(null);
    }

    if (pluginRes.error) {
      setHubError(pluginRes.error);
    } else {
      setPlugins(pluginRes.plugins);
    }

    if (!execRes.error && execRes.executions.length > 0) {
      setExecutions(execRes.executions);
    } else {
      setExecutions(loadSessionExecutionHistory());
    }

    try {
      const opResponse = await fetch(
        integrationHubHttp("/api/v1/automation/operations")
      );
      if (opResponse.ok) {
        const data = await opResponse.json();
        setOperations(
          (data.operations || []).map((o: Record<string, unknown>) =>
            mapOperationFromApi(o)
          )
        );
      }
    } catch {
      /* optional */
    }

    try {
      const monResponse = await fetch(
        integrationHubHttp("/api/v1/automation/monitoring/sessions")
      );
      if (monResponse.ok) {
        const data = await monResponse.json();
        setMonitoringSessions(
          (data.sessions || []).map((s: Record<string, unknown>) =>
            mapMonitoringFromApi(s)
          )
        );
      }
    } catch {
      /* optional */
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 10000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  const loadPluginDetails = async (pluginName: string) => {
    try {
      const response = await fetch(
        integrationHubHttp(`/api/v1/plugins/${pluginName}`)
      );
      if (response.ok) {
        const data = await response.json();
        setPluginDetails(data);
      }
    } catch (error) {
      console.error("Failed to load plugin details:", error);
    }
  };

  const togglePlugin = async (pluginName: string, enabled: boolean) => {
    setActionError(null);
    try {
      const endpoint = enabled ? "enable" : "disable";
      const response = await fetch(
        integrationHubHttp(`/api/v1/plugins/${pluginName}/${endpoint}`),
        { method: "POST" }
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setActionError(
          (body as { error?: string }).error || `Toggle failed (${response.status})`
        );
        return;
      }
      setActionMessage(`${pluginName} ${enabled ? "enabled" : "disabled"}`);
      refreshAll();
    } catch {
      setActionError("Failed to toggle plugin");
    }
  };

  const controlOperation = async (
    operationId: string,
    action: "pause" | "resume" | "stop"
  ) => {
    try {
      const response = await fetch(
        integrationHubHttp("/api/v1/automation/operation/control"),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            operation_id: operationId,
            action: action === "stop" ? "abort" : action,
          }),
        }
      );
      if (response.ok) refreshAll();
    } catch (error) {
      console.error("Failed to control operation:", error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#080c14] text-white flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-cyan-500" />
      </div>
    );
  }

  const pluginsLoaded = plugins.length;
  const pluginsHealthy = plugins.filter((p) => p.healthy).length;

  return (
    <div className="min-h-screen bg-[#080c14] text-white">
      <header className="sticky top-0 z-40 border-b border-slate-800/60 bg-[#080c14]/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-cyan-400">Integration Hub</h1>
              <p className="text-sm text-slate-500">
                Plugin catalog and health — tools run via Autonomous Ops
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                status={hubError ? "danger" : hubHealth?.status === "healthy" ? "success" : "warning"}
                size="sm"
              >
                {hubError ? "Hub unreachable" : `${pluginsHealthy}/${pluginsLoaded} healthy`}
              </StatusBadge>
              <Button
                onClick={() => refreshAll()}
                className="h-8 bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded-lg text-sm"
              >
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8 space-y-8">
        {hubError && (
          <div
            role="alert"
            className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
          >
            <p className="font-medium">Integration Hub error</p>
            <p className="mt-1 text-red-200/90">{hubError}</p>
            <p className="mt-2 text-xs text-red-300/70">
              Expected at {integrationHubHttp("")}
            </p>
          </div>
        )}

        {actionError && (
          <div
            role="alert"
            className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
          >
            {actionError}
          </div>
        )}

        {actionMessage && !actionError && (
          <div className="rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-200">
            {actionMessage}
          </div>
        )}

        <section className="rounded-xl border border-cyan-800/40 bg-cyan-950/20 px-4 py-3 text-sm text-cyan-100/90">
          Offensive tools (Nuclei, ffuf, sqlmap, Metasploit, MCP/Burp, nmap, etc.) are not
          executed from this page. Use{" "}
          <a href="/operations" className="font-medium text-cyan-300 underline hover:text-cyan-200">
            Autonomous Ops
          </a>{" "}
          for AI-driven tool runs; output appears in the unified terminal.
        </section>

        {/* Hub status */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <div>
              <p className="text-xs text-slate-500">Service</p>
              <p className="font-medium text-white">{hubHealth?.service || "integration-hub"}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Plugins loaded</p>
              <p className="font-medium text-white">{hubHealth?.plugin_count ?? pluginsLoaded}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Ready</p>
              <p className="font-medium text-emerald-400">{hubHealth?.plugins_ready ?? "—"}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Endpoint</p>
              <p className="font-mono text-xs text-slate-400 truncate">{integrationHubHttp("/integrations")}</p>
            </div>
          </div>
        </section>

        {/* MCP Servers */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm">
          <h2 className="text-base font-semibold text-white mb-3">MCP Servers</h2>
          <p className="text-xs text-slate-500 mb-4">
            PortSwigger Burp MCP — orchestrator{" "}
            <span className="font-mono text-slate-400">plugin=mcp_burp</span>
          </p>
          {mcpError ? (
            <p className="text-sm text-amber-400">{mcpError}</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
              <div>
                <p className="text-xs text-slate-500">Burp MCP</p>
                <StatusBadge
                  status={
                    mcpStatus?.burp_configured || mcpStatus?.burp_enabled
                      ? "success"
                      : "warning"
                  }
                  size="sm"
                >
                  {mcpStatus?.burp_enabled ? "Enabled" : "Disabled"}
                </StatusBadge>
              </div>
              <div>
                <p className="text-xs text-slate-500">Mode</p>
                <p className="font-medium text-white">
                  {mcpStatus?.mock ? "Mock (MCP_MOCK)" : "Live"}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Servers</p>
                <p className="font-medium text-white">
                  {mcpStatus?.servers?.length ?? 0} registered
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Burp tools</p>
                <p className="font-medium text-emerald-400">
                  {mcpStatus?.mcp_status?.tool_count ?? "—"}
                  {mcpStatus?.mcp_status?.degraded ? " (degraded)" : ""}
                </p>
              </div>
            </div>
          )}
          <p className="mt-3 text-xs text-slate-600">
            MCP_BURP_ENABLED, MCP_BURP_URL or MCP_BURP_COMMAND — see .env.example
          </p>
        </section>

        {/* Plugin catalog */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
          <h2 className="text-base font-semibold text-white mb-4">
            Plugin catalog ({plugins.length})
          </h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {plugins.map((plugin) => {
              const autonomousOnly = OFFENSIVE_TOOL_PLUGINS.has(plugin.name);
              return (
                <div
                  key={plugin.name}
                  className={`rounded-lg border bg-slate-950/30 p-4 transition-all ${
                    plugin.enabled ? "border-cyan-800/60" : "border-slate-800"
                  } hover:border-slate-600`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <h3 className="text-sm font-medium text-white">{plugin.name}</h3>
                      {plugin.category && (
                        <p className="text-[10px] uppercase tracking-wide text-slate-500">
                          {plugin.category}
                        </p>
                      )}
                    </div>
                    <StatusBadge
                      status={plugin.healthy ? "success" : "danger"}
                      size="sm"
                    >
                      {plugin.status || "unknown"}
                    </StatusBadge>
                  </div>
                  {plugin.description && (
                    <p className="text-xs text-slate-500 mb-2 line-clamp-2">{plugin.description}</p>
                  )}
                  {autonomousOnly && (
                    <p className="text-[10px] text-cyan-500/80 mb-2">Autonomous Ops only</p>
                  )}
                  <p className="text-[11px] text-slate-500 mb-2">
                    Last run: {formatRelativeTime(plugin.last_run)}
                    {plugin.version ? ` · v${plugin.version}` : ""}
                  </p>
                  {plugin.capabilities && plugin.capabilities.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3 max-h-16 overflow-hidden">
                      {plugin.capabilities.slice(0, 4).map((cap) => (
                        <span
                          key={cap}
                          className="rounded px-1.5 py-0.5 text-[10px] bg-slate-800 text-slate-400"
                        >
                          {cap}
                        </span>
                      ))}
                      {plugin.capabilities.length > 4 && (
                        <span className="text-[10px] text-slate-500">
                          +{plugin.capabilities.length - 4}
                        </span>
                      )}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <Button
                      onClick={() => togglePlugin(plugin.name, !plugin.enabled)}
                      className={`h-7 flex-1 text-[11px] rounded-md ${
                        plugin.enabled
                          ? "bg-amber-600 hover:bg-amber-700"
                          : "bg-emerald-600 hover:bg-emerald-700"
                      }`}
                    >
                      {plugin.enabled ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      onClick={() => {
                        setSelectedPlugin(plugin.name);
                        loadPluginDetails(plugin.name);
                      }}
                      className="h-7 bg-slate-700 hover:bg-slate-600 text-[11px] px-3 rounded-md"
                    >
                      Details
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Execution history */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
          <h2 className="text-base font-semibold text-white mb-4">
            Recent executions ({executions.length})
          </h2>
          {executions.length === 0 ? (
            <p className="text-sm text-slate-500">No executions yet this session.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="text-xs text-slate-500 border-b border-slate-800">
                    <th className="py-2 pr-4">Time</th>
                    <th className="py-2 pr-4">Plugin</th>
                    <th className="py-2 pr-4">Operation</th>
                    <th className="py-2 pr-4">Target</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {executions.slice(0, 20).map((ex) => (
                    <tr key={ex.id} className="border-b border-slate-800/50">
                      <td className="py-2 pr-4 text-slate-400 text-xs">
                        {formatRelativeTime(ex.created_at)}
                      </td>
                      <td className="py-2 pr-4 text-white">{ex.plugin_name}</td>
                      <td className="py-2 pr-4 text-slate-400">{ex.operation || "—"}</td>
                      <td className="py-2 pr-4 text-slate-300 truncate max-w-[140px]">
                        {ex.target}
                      </td>
                      <td className="py-2">
                        <StatusBadge
                          status={ex.success ? "success" : "danger"}
                          size="sm"
                        >
                          {ex.success ? "OK" : "Fail"}
                        </StatusBadge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Active operations */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
          <h2 className="text-base font-semibold text-white mb-4">
            Active operations ({operations.length})
          </h2>
          {operations.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-800 py-12 text-center">
              <p className="text-sm text-slate-400">No active operations</p>
            </div>
          ) : (
            <div className="space-y-4">
              {operations.map((operation) => (
                <div
                  key={operation.id}
                  className="rounded-lg border border-slate-800 bg-slate-950/30 p-4"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="text-sm font-medium text-white">{operation.type}</h3>
                      <p className="text-xs text-slate-500">
                        {operation.target || "No target"} · {operation.id.slice(0, 12)}
                      </p>
                    </div>
                    <StatusBadge
                      status={
                        operation.status === "running"
                          ? "success"
                          : operation.status === "completed"
                            ? "info"
                            : operation.status === "failed"
                              ? "danger"
                              : "warning"
                      }
                      size="sm"
                    >
                      {operation.status}
                    </StatusBadge>
                  </div>
                  {operation.status === "running" && (
                    <>
                      <div className="w-full bg-slate-800 rounded-full h-2 mb-3">
                        <div
                          className="bg-cyan-500 h-2 rounded-full transition-all"
                          style={{ width: `${operation.progress}%` }}
                        />
                      </div>
                      <div className="flex gap-2">
                        <Button
                          onClick={() => controlOperation(operation.id, "pause")}
                          className="h-7 bg-amber-600 text-[11px]"
                        >
                          Pause
                        </Button>
                        <Button
                          onClick={() => controlOperation(operation.id, "stop")}
                          className="h-7 bg-red-600 text-[11px]"
                        >
                          Stop
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Monitoring */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
          <h2 className="text-base font-semibold text-white mb-4">
            Monitoring sessions ({monitoringSessions.length})
          </h2>
          {monitoringSessions.length === 0 ? (
            <p className="text-sm text-slate-500">No active monitoring sessions</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {monitoringSessions.map((session) => (
                <div
                  key={session.id}
                  className="rounded-lg border border-slate-800 bg-slate-950/30 p-4"
                >
                  <div className="flex justify-between mb-2">
                    <h3 className="text-sm font-medium">{session.target}</h3>
                    <StatusBadge
                      status={session.status === "active" ? "success" : "neutral"}
                      size="sm"
                    >
                      {session.status}
                    </StatusBadge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {selectedPlugin && pluginDetails && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-slate-900 rounded-xl border border-slate-800 p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
              <div className="flex justify-between mb-4">
                <h2 className="text-base font-semibold">{selectedPlugin}</h2>
                <Button
                  onClick={() => {
                    setSelectedPlugin(null);
                    setPluginDetails(null);
                  }}
                  className="h-8 bg-slate-700 text-xs"
                >
                  Close
                </Button>
              </div>
              {Boolean(pluginDetails.description) && (
                <p className="text-sm text-slate-300 mb-4">
                  {String(pluginDetails.description)}
                </p>
              )}
              {(pluginDetails.capabilities as string[] | undefined)?.length ? (
                <div className="flex flex-wrap gap-2">
                  {(pluginDetails.capabilities as string[]).map((cap) => (
                    <span
                      key={cap}
                      className="rounded-full px-2.5 py-0.5 text-xs bg-cyan-500/10 text-cyan-400"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              ) : null}
              {pluginDetails.health != null && (
                <pre className="mt-4 text-xs text-slate-400 overflow-auto">
                  {JSON.stringify(pluginDetails.health, null, 2)}
                </pre>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
