"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ListChecks, Target, Radar } from "lucide-react";
import { orchestratorFetchInit, orchestratorHttp, orchestratorWs } from "@/lib/config";

interface ServiceStatus {
  name: string;
  port: number;
  status: "healthy" | "unhealthy" | "unknown";
  uptime?: string;
  lastCheck?: string;
  error?: string;
}

interface Engagement {
  id: string;
  target: string;
  status: "running" | "completed" | "failed" | "cancelled";
  startTime: string;
  progress: number;
  endTime?: string;
  error?: string;
}

interface Toast {
  id: string;
  type: "success" | "error" | "warning" | "info";
  message: string;
  duration?: number;
}

const SERVICE_ICONS: Record<string, string> = {
  "Knowledge Engine": "🧠",
  "Real-time Analyzer": "📡",
  "OpSec Monitor": "🛡️",
  "Orchestrator": "🎼",
  "Integration Hub": "🔌",
  "PostgreSQL": "🐘",
  "Qdrant": "🔍",
};

function ServiceCard({ service, index }: { service: ServiceStatus; index: number }) {
  const isHealthy = service.status === "healthy";
  const isChecking = service.status === "unknown";

  return (
    <div
      className="group relative rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm transition-all duration-300 hover:border-slate-600 hover:bg-slate-800/60 hover:shadow-lg hover:shadow-cyan-500/5"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-lg transition-colors duration-300 ${
            isHealthy
              ? "bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500/20"
              : isChecking
              ? "bg-slate-700/50 text-slate-400"
              : "bg-red-500/10 text-red-400 group-hover:bg-red-500/20"
          }`}>
            {SERVICE_ICONS[service.name] || "⚙️"}
          </div>
          <div>
            <h3 className="font-semibold text-sm text-slate-200">{service.name}</h3>
            <p className="text-xs text-slate-500">Port {service.port}</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
            isHealthy
              ? "bg-emerald-500/10 text-emerald-400"
              : isChecking
              ? "bg-slate-700/50 text-slate-400"
              : "bg-red-500/10 text-red-400"
          }`}>
            <span className={`h-1.5 w-1.5 rounded-full ${isChecking ? "animate-pulse bg-slate-400" : isHealthy ? "bg-emerald-400" : "bg-red-400"}`} />
            {isHealthy ? "Healthy" : isChecking ? "Checking" : "Unhealthy"}
          </span>
          {service.lastCheck && (
            <span className="text-[10px] text-slate-600">
              {new Date(service.lastCheck).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>
      {service.error && (
        <div className="mt-3 rounded-lg border border-red-500/10 bg-red-500/5 px-3 py-2">
          <p className="text-xs text-red-400/80 truncate">{service.error}</p>
        </div>
      )}
    </div>
  );
}

function EngagementSkeleton() {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 animate-pulse">
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <div className="h-5 w-32 rounded bg-slate-700/50" />
          <div className="h-4 w-48 rounded bg-slate-700/50" />
        </div>
        <div className="h-8 w-20 rounded bg-slate-700/50" />
      </div>
      <div className="mt-4 h-2 w-full rounded-full bg-slate-700/50" />
    </div>
  );
}

function EngagementCard({ engagement, onCancel, onRetry, onDelete, onView }: {
  engagement: Engagement;
  onCancel: () => void;
  onRetry: () => void;
  onDelete: () => void;
  onView: () => void;
}) {
  const statusConfig = {
    running: { bg: "bg-amber-500/10", text: "text-amber-400", border: "border-amber-500/20", dot: "bg-amber-400 animate-pulse", label: "In Progress" },
    completed: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/20", dot: "bg-emerald-400", label: "Completed" },
    failed: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/20", dot: "bg-red-400", label: "Failed" },
    cancelled: { bg: "bg-slate-700/30", text: "text-slate-400", border: "border-slate-600/20", dot: "bg-slate-400", label: "Cancelled" },
  };
  const config = statusConfig[engagement.status];

  return (
    <div className="group relative rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm transition-all duration-300 hover:border-slate-600 hover:bg-slate-800/60 hover:shadow-lg hover:shadow-cyan-500/5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="font-semibold text-white truncate">{engagement.target}</h3>
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${config.bg} ${config.text} border ${config.border}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
              {config.label}
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Started {new Date(engagement.startTime).toLocaleString()}
          </p>
          {engagement.endTime && (
            <p className="text-xs text-slate-600 mt-0.5">
              Ended {new Date(engagement.endTime).toLocaleString()}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {engagement.status === "running" && (
            <Button onClick={onCancel} size="sm" variant="outline" className="h-8 border-amber-500/30 text-amber-400 hover:bg-amber-500/10 hover:text-amber-300">
              Cancel
            </Button>
          )}
          {engagement.status === "failed" && (
            <Button onClick={onRetry} size="sm" variant="outline" className="h-8 border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 hover:text-cyan-300">
              Retry
            </Button>
          )}
          {engagement.status === "completed" && (
            <Button onClick={onView} size="sm" className="h-8 bg-gradient-to-r from-cyan-600 to-blue-600 text-white hover:from-cyan-500 hover:to-blue-500">
              View
            </Button>
          )}
          <Button onClick={onDelete} size="sm" variant="ghost" className="h-8 text-slate-500 hover:text-red-400 hover:bg-red-500/10">
            Delete
          </Button>
        </div>
      </div>

      {engagement.status === "running" && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-medium text-slate-400">{engagement.progress}%</span>
            <span className="text-[10px] text-slate-600">Processing...</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-700 ease-out"
              style={{ width: `${engagement.progress}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: "Knowledge Engine", port: 8000, status: "unknown" },
    { name: "Real-time Analyzer", port: 8001, status: "unknown" },
    { name: "OpSec Monitor", port: 8002, status: "unknown" },
    { name: "Orchestrator", port: 3001, status: "unknown" },
    { name: "Integration Hub", port: 8500, status: "unknown" },
    { name: "PostgreSQL", port: 5432, status: "unknown" },
    { name: "Qdrant", port: 6333, status: "unknown" },
  ]);

  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [targetInput, setTargetInput] = useState("");
  const [aggressionLevel, setAggressionLevel] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [initialLoad, setInitialLoad] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("opsecai_engagements");
    if (saved) {
      try { setEngagements(JSON.parse(saved)); } catch {}
    }
    setInitialLoad(false);
  }, []);

  useEffect(() => {
    if (!initialLoad) {
      localStorage.setItem("opsecai_engagements", JSON.stringify(engagements));
    }
  }, [engagements, initialLoad]);

  const addToast = useCallback((type: Toast["type"], message: string, duration = 5000) => {
    const id = Date.now().toString();
    setToasts((prev) => [...prev, { id, type, message, duration }]);
    if (duration > 0) {
      setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), duration);
    }
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const checkServiceHealth = useCallback(async (retryCount = 0) => {
    const maxRetries = 2;
    try {
      const healthChecks = await Promise.allSettled(
        services.map(async (service) => {
          try {
            let endpoint = "/health";
            if (service.name === "Qdrant") endpoint = "/healthz";
            else if (service.name === "PostgreSQL") {
              return { name: service.name, status: "healthy" as const, error: undefined };
            }
            const response = await fetch(`http://localhost:${service.port}${endpoint}`, {
              method: "GET",
              signal: AbortSignal.timeout(5000),
            });
            if (response.ok) {
              return { name: service.name, status: "healthy" as const, error: undefined };
            }
            return { name: service.name, status: "unhealthy" as const, error: `HTTP ${response.status}` };
          } catch (error) {
            return { name: service.name, status: "unhealthy" as const, error: error instanceof Error ? error.message : "Connection failed" };
          }
        })
      );

      const updated = services.map((service) => {
        const result = healthChecks.find(
          (r) => r.status === "fulfilled" && r.value.name === service.name
        );
        if (result?.status === "fulfilled") {
          return { ...service, status: result.value.status, lastCheck: new Date().toISOString(), error: result.value.error };
        }
        return { ...service, status: "unhealthy" as const, lastCheck: new Date().toISOString(), error: "Health check failed" };
      });
      setServices(updated);

      const unhealthy = updated.filter((s) => s.status === "unhealthy");
      if (unhealthy.length > 0 && retryCount === 0) {
        addToast("warning", `${unhealthy.length} service(s) unhealthy. Retrying...`);
      }
    } catch (error) {
      setServices((prev) => prev.map((s) => ({ ...s, status: "unhealthy" as const, lastCheck: new Date().toISOString(), error: "Health check failed" })));
      if (retryCount < maxRetries) {
        setTimeout(() => checkServiceHealth(retryCount + 1), 2000);
      }
    }
  }, [services, addToast]);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await checkServiceHealth();
    setIsRefreshing(false);
    addToast("success", "Service status refreshed");
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    const delay = setTimeout(() => checkServiceHealth(), 3000);
    const interval = setInterval(checkServiceHealth, 30000);
    return () => { clearTimeout(delay); clearInterval(interval); };
  }, [checkServiceHealth]);

  const engagementWebSockets = useRef<Map<string, WebSocket>>(new Map());

  const connectToEngagementWebSocket = useCallback((engagementId: string) => {
    const existing = engagementWebSockets.current.get(engagementId);
    if (existing) existing.close();
    try {
      const ws = new WebSocket(`${orchestratorWs("/")}?engagement=${engagementId}`);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.id || data.engagement_id) {
            const id = data.id || data.engagement_id;
            const statusMap: Record<string, Engagement["status"]> = {
              starting: "running", scanning: "running", building_vectors: "running",
              assessing_opsec: "running", auditing_opsec: "running", ai_analysis: "running",
              complete: "completed", error: "failed", cancelled: "cancelled",
            };
            const progressMap: Record<string, number> = {
              starting: 5, scanning: 20, building_vectors: 40, assessing_opsec: 60,
              auditing_opsec: 80, ai_analysis: 90, complete: 100, error: 0, cancelled: 0,
            };
            const s = statusMap[data.status] || "running";
            const p = progressMap[data.status] || 0;
            setEngagements((prev) => prev.map((e) => e.id === id ? { ...e, status: s, progress: p, endTime: s === "completed" || s === "failed" || s === "cancelled" ? new Date().toISOString() : e.endTime } : e));
            if (data.status === "complete") { addToast("success", `Engagement for ${data.target} completed`); ws.close(); engagementWebSockets.current.delete(id); }
            else if (data.status === "error") { addToast("error", `Engagement for ${data.target} failed`); ws.close(); engagementWebSockets.current.delete(id); }
          }
        } catch {}
      };
      ws.onclose = () => engagementWebSockets.current.delete(engagementId);
      engagementWebSockets.current.set(engagementId, ws);
    } catch {}
  }, [addToast]);

  useEffect(() => {
    return () => {
      engagementWebSockets.current.forEach((ws) => ws.close());
      engagementWebSockets.current.clear();
    };
  }, []);

  const startEngagement = useCallback(async () => {
    if (!targetInput.trim()) { addToast("error", "Please enter a target"); return; }
    const trimmed = targetInput.trim();
    const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$|^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$|^localhost$/;
    if (!ipRegex.test(trimmed)) { addToast("error", "Invalid IP or hostname format"); return; }

    setIsLoading(true);
    try {
      const response = await fetch(orchestratorHttp("/engage"), orchestratorFetchInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: trimmed, aggression_level: aggressionLevel }),
      }));
      if (response.ok) {
        const data = await response.json();
        const newEngagement: Engagement = {
          id: data.engagement_id || Date.now().toString(),
          target: trimmed,
          status: "running",
          startTime: new Date().toISOString(),
          progress: 5,
        };
        setEngagements((prev) => [newEngagement, ...prev]);
        setTargetInput("");
        addToast("success", `Engagement started for ${trimmed}`);
        connectToEngagementWebSocket(newEngagement.id);
      } else {
        const text = await response.text();
        addToast("error", text || "Failed to start engagement");
      }
    } catch {
      addToast("error", "Failed to start engagement");
    } finally {
      setIsLoading(false);
    }
  }, [targetInput, aggressionLevel, addToast, connectToEngagementWebSocket]);

  const cancelEngagement = (id: string) => {
    const ws = engagementWebSockets.current.get(id);
    if (ws) { ws.close(); engagementWebSockets.current.delete(id); }
    setEngagements((prev) => prev.map((e) => e.id === id ? { ...e, status: "cancelled" as const, endTime: new Date().toISOString() } : e));
    addToast("info", "Engagement cancelled");
  };

  const deleteEngagement = (id: string) => {
    setEngagements((prev) => prev.filter((e) => e.id !== id));
    addToast("info", "Engagement deleted");
  };

  const retryEngagement = (engagement: Engagement) => {
    setTargetInput(engagement.target);
    deleteEngagement(engagement.id);
    addToast("info", "Ready to retry - click Start Engagement");
  };

  const healthyCount = services.filter((s) => s.status === "healthy").length;
  const isAllHealthy = healthyCount === services.length;

  const quickLinks = [
    { href: "/operations", label: "Autonomous Ops", icon: Target, desc: "Assessment, chains, MITRE — unified" },
    { href: "/scanner", label: "Scanner", icon: Radar, desc: "Network reconnaissance" },
    { href: "/integration-hub", label: "Integration Hub", icon: ListChecks, desc: "Plugin catalog and health" },
  ];

  return (
    <div className="space-y-10 text-white">
      {/* Toasts */}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 rounded-xl border px-5 py-3 shadow-2xl backdrop-blur-xl transition-all duration-300 animate-in slide-in-from-right fade-in ${
              toast.type === "success" ? "border-emerald-500/20 bg-emerald-950/80 text-emerald-100" :
              toast.type === "error" ? "border-red-500/20 bg-red-950/80 text-red-100" :
              toast.type === "warning" ? "border-amber-500/20 bg-amber-950/80 text-amber-100" :
              "border-cyan-500/20 bg-slate-900/80 text-slate-100"
            }`}
            role="alert"
          >
            <span className="text-sm font-medium">{toast.message}</span>
            <button onClick={() => removeToast(toast.id)} className="ml-2 text-lg leading-none opacity-60 hover:opacity-100">×</button>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Command center</h1>
          <p className="text-sm text-slate-500">Service health, engagements, and quick access</p>
        </div>
        <div className="flex items-center gap-3">
<div className="hidden items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-1.5 md:flex">
              <span className={`h-2 w-2 rounded-full ${isAllHealthy ? "bg-emerald-400" : healthyCount > 0 ? "bg-amber-400" : "bg-red-400"} ${!isAllHealthy ? "animate-pulse" : ""}`} />
              <span className="text-xs text-slate-400">
                {isAllHealthy ? "All systems operational" : `${healthyCount}/${services.length} operational`}
              </span>
            </div>
            <Button
              onClick={handleManualRefresh}
              disabled={isRefreshing}
              size="sm"
              className="h-8 bg-gradient-to-r from-cyan-600 to-blue-600 text-xs text-white hover:from-cyan-500 hover:to-blue-500"
            >
              {isRefreshing ? "Refreshing..." : "Refresh"}
            </Button>
        </div>
      </div>

      <section>
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-white">Quick access</h2>
          <p className="text-xs text-slate-500">Jump to primary workflows</p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {quickLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="group rounded-xl border border-slate-800 bg-slate-900/60 p-4 transition-all hover:border-cyan-500/30 hover:bg-slate-800/60"
            >
              <link.icon className="mb-2 h-5 w-5 text-cyan-400" />
              <p className="text-sm font-medium text-slate-200 group-hover:text-white">{link.label}</p>
              <p className="mt-1 text-xs text-slate-500">{link.desc}</p>
            </Link>
          ))}
        </div>
      </section>

        {/* Service Status */}
        <section className="mb-10">
          <div className="mb-5 flex items-end justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Service Status</h2>
              <p className="text-xs text-slate-500">Real-time system health</p>
            </div>
            <span className="text-xs text-slate-600">{healthyCount}/{services.length} healthy</span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {services.map((service, i) => (
              <ServiceCard key={service.name} service={service} index={i} />
            ))}
          </div>
        </section>

        {/* Start Engagement */}
        <section className="mb-10">
          <div className="mb-5">
            <h2 className="text-lg font-semibold text-white">Start New Engagement</h2>
            <p className="text-xs text-slate-500">Initiate security assessment</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
            <div className="grid gap-4 md:grid-cols-12">
              <div className="md:col-span-5">
                <label className="mb-1.5 block text-xs font-medium text-slate-400">Target</label>
                <input
                  type="text"
                  value={targetInput}
                  onChange={(e) => setTargetInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && startEngagement()}
                  placeholder="IP or hostname (e.g. 192.168.1.10)"
                  disabled={isLoading}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 transition-colors focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
                />
              </div>
              <div className="md:col-span-3">
                <label className="mb-1.5 block text-xs font-medium text-slate-400">Aggression</label>
                <select
                  value={aggressionLevel}
                  onChange={(e) => setAggressionLevel(parseInt(e.target.value))}
                  disabled={isLoading}
                  className="w-full appearance-none rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white transition-colors focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
                >
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((l) => (
                    <option key={l} value={l}>Level {l}</option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="mb-1.5 block text-xs font-medium text-slate-400">Risk</label>
                <div className={`flex h-[42px] items-center justify-center rounded-lg border text-sm font-medium ${
                  aggressionLevel <= 3
                    ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-400"
                    : aggressionLevel <= 7
                    ? "border-amber-500/20 bg-amber-500/5 text-amber-400"
                    : "border-red-500/20 bg-red-500/5 text-red-400"
                }`}>
                  {aggressionLevel <= 3 ? "Conservative" : aggressionLevel <= 7 ? "Moderate" : "Aggressive"}
                </div>
              </div>
              <div className="md:col-span-2 flex items-end">
                <Button
                  onClick={startEngagement}
                  disabled={isLoading || !targetInput.trim()}
                  className="h-[42px] w-full bg-gradient-to-r from-cyan-600 to-blue-600 text-sm font-medium text-white transition-all hover:from-cyan-500 hover:to-blue-500 hover:shadow-lg hover:shadow-cyan-500/20 disabled:opacity-50"
                >
                  {isLoading ? "Starting..." : "Start"}
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* Engagements */}
        <section className="mb-10">
          <div className="mb-5 flex items-end justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Engagements</h2>
              <p className="text-xs text-slate-500">Active and recent assessments</p>
            </div>
            {engagements.length > 0 && (
              <Button
                onClick={() => { if (confirm("Clear all engagements?")) { setEngagements([]); addToast("info", "All cleared"); } }}
                variant="ghost"
                size="sm"
                className="text-xs text-slate-500 hover:text-slate-300"
              >
                Clear All
              </Button>
            )}
          </div>

          {initialLoad ? (
            <div className="space-y-3">
              <EngagementSkeleton />
              <EngagementSkeleton />
            </div>
          ) : engagements.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-slate-900/30 py-16 text-center">
              <div className="mb-3 text-4xl opacity-40">🎯</div>
              <p className="text-sm text-slate-500">No engagements yet</p>
              <p className="text-xs text-slate-600 mt-1">Enter a target above to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {engagements.map((engagement) => (
                <EngagementCard
                  key={engagement.id}
                  engagement={engagement}
                  onCancel={() => cancelEngagement(engagement.id)}
                  onRetry={() => retryEngagement(engagement)}
                  onDelete={() => deleteEngagement(engagement.id)}
                  onView={() => { window.location.href = `/engagement/${engagement.id}`; }}
                />
              ))}
            </div>
          )}
        </section>


    </div>
  );
}
