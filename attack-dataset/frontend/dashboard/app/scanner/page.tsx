"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  AnalyzerHealth,
  AnalyzerSession,
  SCAN_TYPE_OPTIONS,
  ScanType,
  cacheSessionId,
  fetchAnalyzerHealth,
  fetchSession,
  fetchSessions,
  fingerprintExportUrl,
  isAdaptiveScanType,
  isSessionActive,
  loadCachedSessionIds,
  startScan,
  statusLabel,
} from "@/lib/analyzer";

function statusBadgeVariant(
  status: AnalyzerSession["status"]
): "success" | "warning" | "danger" | "info" | "neutral" {
  switch (status) {
    case "ready":
      return "success";
    case "scanning":
    case "analysing":
      return "warning";
    case "error":
      return "danger";
    default:
      return "neutral";
  }
}

function formatDuration(sec?: number): string {
  if (sec == null || sec <= 0) return "—";
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

export default function Scanner() {
  const [sessions, setSessions] = useState<AnalyzerSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<AnalyzerSession | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [targetInput, setTargetInput] = useState("");
  const [timeoutInput, setTimeoutInput] = useState("45");
  const [scanType, setScanType] = useState<ScanType>("default");
  const [aggression, setAggression] = useState(5);
  const [isScanning, setIsScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [health, setHealth] = useState<AnalyzerHealth | null>(null);
  const [healthError, setHealthError] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshHealth = useCallback(async () => {
    const h = await fetchAnalyzerHealth();
    setHealth(h);
    setHealthError(!h || h.status !== "ok");
  }, []);

  const loadSessions = useCallback(async () => {
    const list = await fetchSessions();
    setSessions(list);
    if (activeSessionId) {
      const active = list.find((s) => s.id === activeSessionId);
      if (active) {
        setSelectedSession((prev) =>
          prev?.id === active.id ? { ...active, vectors: active.vectors ?? prev.vectors } : prev
        );
        if (!isSessionActive(active.status)) {
          setActiveSessionId(null);
        }
      }
    }
  }, [activeSessionId]);

  const pollActiveSession = useCallback(async () => {
    if (!activeSessionId) return;
    const sess = await fetchSession(activeSessionId);
    if (!sess) return;
    setSelectedSession(sess);
    setSessions((prev) => {
      const idx = prev.findIndex((s) => s.id === sess.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = sess;
        return next;
      }
      return [sess, ...prev];
    });
    if (!isSessionActive(sess.status)) {
      setActiveSessionId(null);
    }
  }, [activeSessionId]);

  useEffect(() => {
    loadSessions();
    refreshHealth();
    const cached = loadCachedSessionIds();
    if (cached.length > 0 && !selectedSession) {
      void fetchSession(cached[0]).then((s) => {
        if (s) setSelectedSession(s);
      });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      void loadSessions();
      void refreshHealth();
      void pollActiveSession();
    }, 2500);
    return () => clearInterval(interval);
  }, [autoRefresh, loadSessions, refreshHealth, pollActiveSession]);

  useEffect(() => {
    if (!activeSessionId) {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
      return;
    }
    void pollActiveSession();
    pollRef.current = setInterval(() => void pollActiveSession(), 1500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeSessionId, pollActiveSession]);

  const handleStartScan = async () => {
    if (!targetInput.trim()) return;
    setIsScanning(true);
    setScanError(null);
    const timeout = Math.max(15, parseInt(timeoutInput, 10) || 45);
    const { session, error } = await startScan({
      target: targetInput.trim(),
      scan_timeout_sec: timeout,
      scan_type: scanType,
      aggression_level: aggression,
    });
    setIsScanning(false);
    if (error || !session) {
      setScanError(error || "Failed to start scan");
      return;
    }
    setTargetInput("");
    setActiveSessionId(session.id);
    setSelectedSession(session);
    cacheSessionId(session.id);
    await loadSessions();
  };

  const viewSession = async (sessionId: string) => {
    const data = await fetchSession(sessionId);
    if (data) {
      setSelectedSession(data);
      if (isSessionActive(data.status)) setActiveSessionId(sessionId);
    }
  };

  const removeFromList = (sessionId: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (selectedSession?.id === sessionId) setSelectedSession(null);
    if (activeSessionId === sessionId) setActiveSessionId(null);
  };

  const runningCount = sessions.filter((s) => isSessionActive(s.status)).length;

  return (
    <div className="min-h-screen bg-[#080c14] text-white">
      <header className="sticky top-0 z-40 border-b border-slate-800/60 bg-[#080c14]/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-cyan-400">Real-time Scanner</h1>
              <p className="text-sm text-slate-500">
                Network reconnaissance, fingerprinting, and Knowledge Engine attack vectors
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <HealthWidget health={health} error={healthError} onRefresh={refreshHealth} />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded"
                />
                <span className="text-slate-500">Live refresh</span>
              </label>
              <Button
                onClick={() => {
                  void loadSessions();
                  void refreshHealth();
                }}
                className="h-8 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm"
              >
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {activeSessionId && (
          <div className="mb-6 flex items-center gap-3 rounded-lg border border-cyan-500/20 bg-cyan-950/20 px-4 py-3">
            <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
            <p className="text-sm text-cyan-200">
              Live polling session <span className="font-mono text-cyan-400">{activeSessionId}</span>
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
              <h2 className="mb-4 text-base font-semibold text-white">Start New Scan</h2>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <label className="mb-1.5 block text-xs font-medium text-slate-400">Target</label>
                  <input
                    type="text"
                    value={targetInput}
                    onChange={(e) => setTargetInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && void handleStartScan()}
                    placeholder="IP, hostname, or CIDR (e.g. 10.0.0.0/24)"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-slate-400">Scan type</label>
                  <select
                    value={scanType}
                    onChange={(e) => setScanType(e.target.value as ScanType)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white focus:border-cyan-500/50 focus:outline-none"
                  >
                    {SCAN_TYPE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label} — {o.hint}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-slate-400">
                    Timeout (seconds)
                  </label>
                  <input
                    type="number"
                    min={15}
                    max={600}
                    value={timeoutInput}
                    onChange={(e) => setTimeoutInput(e.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white focus:border-cyan-500/50 focus:outline-none"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="mb-1.5 block text-xs font-medium text-slate-400">
                    Aggression ({aggression}/10)
                  </label>
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={aggression}
                    onChange={(e) => setAggression(parseInt(e.target.value, 10))}
                    className="w-full accent-cyan-500"
                  />
                  <p className="mt-1 text-[11px] text-slate-500">
                    Maps to nmap timing: higher aggression uses faster scan templates (orchestrator
                    adaptive pivots use typed scans at level 10).
                  </p>
                </div>
              </div>
              {scanError && (
                <p className="mt-3 text-sm text-red-400" role="alert">
                  {scanError}
                </p>
              )}
              <Button
                onClick={() => void handleStartScan()}
                disabled={isScanning || !targetInput.trim()}
                className="mt-4 h-9 bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-2 rounded-lg"
              >
                {isScanning ? "Starting…" : "Start Scan"}
              </Button>
            </section>

            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-white">
                  Scan History ({sessions.length})
                </h2>
                <span className="text-xs text-slate-500">{runningCount} active</span>
              </div>

              {sessions.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-800 py-16 text-center">
                  <p className="text-sm text-slate-400">No scan sessions yet</p>
                  <p className="mt-2 text-xs text-slate-500">
                    Sessions persist in the analyzer process; recent IDs are cached locally
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {sessions.map((session) => (
                    <div
                      key={session.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => void viewSession(session.id)}
                      onKeyDown={(e) => e.key === "Enter" && void viewSession(session.id)}
                      className={`cursor-pointer rounded-lg border bg-slate-950/30 p-4 transition-all ${
                        selectedSession?.id === session.id
                          ? "border-cyan-600"
                          : "border-slate-800 hover:border-slate-600"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-medium text-white">{session.target}</h3>
                            {isAdaptiveScanType(session.scan_type) && (
                              <span className="rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] font-medium text-purple-300">
                                Adaptive type
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-slate-500">
                            {session.id} · {new Date(session.started_at).toLocaleString()}
                            {session.duration_sec != null &&
                              ` · ${formatDuration(session.duration_sec)}`}
                          </p>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <StatusBadge
                            status={
                              session.status === "ready"
                                ? "success"
                                : isSessionActive(session.status)
                                  ? "warning"
                                  : session.status === "error"
                                    ? "danger"
                                    : "neutral"
                            }
                            size="sm"
                            pulse={isSessionActive(session.status)}
                          >
                            {statusLabel(session.status)}
                          </StatusBadge>
                          {(session.service_count ?? session.fingerprint?.services?.length) != null && (
                            <span className="text-xs text-slate-500">
                              {session.service_count ?? session.fingerprint?.services?.length}{" "}
                              services
                            </span>
                          )}
                        </div>
                      </div>
                      {session.error && (
                        <p className="mt-2 text-xs text-red-400">{session.error}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className="lg:col-span-1">
            {selectedSession ? (
              <SessionDetailsPanel
                session={selectedSession}
                onClose={() => setSelectedSession(null)}
                onRemove={() => removeFromList(selectedSession.id)}
              />
            ) : (
              <section className="sticky top-24 rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
                <div className="rounded-xl border border-dashed border-slate-800 py-16 text-center">
                  <p className="text-sm text-slate-400">Select a scan session</p>
                  <p className="mt-2 text-xs text-slate-500">Click a session or start a new scan</p>
                </div>
              </section>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function HealthWidget({
  health,
  error,
  onRefresh,
}: {
  health: AnalyzerHealth | null;
  error: boolean;
  onRefresh: () => void;
}) {
  return (
    <button
      type="button"
      onClick={() => void onRefresh()}
      className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-xs transition-colors ${
        error
          ? "border-red-500/30 bg-red-950/20"
          : "border-emerald-500/30 bg-emerald-950/20 hover:border-emerald-500/50"
      }`}
    >
      <span
        className={`h-2 w-2 rounded-full ${error ? "bg-red-400" : "bg-emerald-400"}`}
      />
      <span className={error ? "text-red-300" : "text-emerald-300"}>
        {error ? "Analyzer offline" : "Analyzer healthy"}
      </span>
      {health && !error && (
        <span className="text-slate-500">
          · {health.active_sessions ?? 0} sessions
          {health.nmap_available === false && " · nmap missing"}
        </span>
      )}
    </button>
  );
}

function SessionDetailsPanel({
  session,
  onClose,
  onRemove,
}: {
  session: AnalyzerSession;
  onClose: () => void;
  onRemove: () => void;
}) {
  const fp = session.fingerprint;
  const chains = session.vectors?.chains ?? [];
  const ports = fp?.services?.map((s) => s.port).filter(Boolean) ?? [];

  return (
    <section className="sticky top-24 space-y-4 rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-white">Session Details</h2>
        <Button
          onClick={onClose}
          className="h-8 bg-slate-700 hover:bg-slate-600 text-white px-2 py-1 rounded text-xs"
        >
          Close
        </Button>
      </div>

      <div className="space-y-3">
        <Row label="Target" value={session.target} />
        <Row label="IP" value={fp?.ip || "—"} />
        <Row label="OS" value={fp?.os || "Unknown"} />
        <div>
          <p className="text-xs text-slate-500">Status</p>
          <StatusBadge status={statusBadgeVariant(session.status)} size="sm" pulse={isSessionActive(session.status)}>
            {statusLabel(session.status)}
          </StatusBadge>
        </div>
        <Row label="Duration" value={formatDuration(session.duration_sec)} />
        <Row
          label="Services / Ports"
          value={`${session.service_count ?? fp?.services?.length ?? 0} / ${session.open_port_count ?? ports.length}`}
        />
        {session.scan_type && <Row label="Scan type" value={session.scan_type} />}
        {session.aggression_level != null && session.aggression_level > 0 && (
          <Row label="Aggression" value={`${session.aggression_level}/10`} />
        )}
      </div>

      {ports.length > 0 && (
        <div>
          <p className="mb-2 text-xs text-slate-500">Open ports</p>
          <div className="flex flex-wrap gap-1.5">
            {ports.map((p) => (
              <span
                key={p}
                className="rounded border border-cyan-500/20 bg-cyan-950/30 px-2 py-0.5 font-mono text-xs text-cyan-300"
              >
                {p}
              </span>
            ))}
          </div>
        </div>
      )}

      {fp?.services && fp.services.length > 0 && (
        <div>
          <p className="mb-2 text-xs text-slate-500">Services ({fp.services.length})</p>
          <div className="max-h-48 space-y-2 overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-slate-500">
                  <th className="pb-1 pr-2">Port</th>
                  <th className="pb-1 pr-2">Service</th>
                  <th className="pb-1">Product</th>
                </tr>
              </thead>
              <tbody>
                {fp.services.map((svc, idx) => (
                  <tr key={idx} className="border-t border-slate-800/80 text-slate-300">
                    <td className="py-1.5 pr-2 font-mono text-cyan-400">
                      {svc.port}/{svc.protocol}
                    </td>
                    <td className="py-1.5 pr-2">{svc.name || "—"}</td>
                    <td className="py-1.5 text-slate-500">
                      {[svc.product, svc.version].filter(Boolean).join(" ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {chains.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-purple-300">
            Suggested attack vectors (Knowledge Engine)
          </p>
          <div className="max-h-56 space-y-2 overflow-y-auto">
            {chains.map((chain) => (
              <div
                key={chain.chain_id}
                className="rounded-lg border border-purple-500/20 bg-purple-950/20 p-3"
              >
                <p className="text-xs font-medium text-white">
                  {chain.chain_id}
                  {chain.confidence != null && (
                    <span className="ml-2 text-slate-500">
                      {(chain.confidence * 100).toFixed(0)}% conf.
                    </span>
                  )}
                </p>
                {chain.steps?.slice(0, 2).map((step, i) => (
                  <p key={i} className="mt-1 text-[11px] text-slate-400">
                    {step.phase}: {step.attack?.title || step.rationale || "—"}
                  </p>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {session.error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/20 p-3">
          <p className="text-xs text-red-400">{session.error}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          onClick={onRemove}
          className="h-8 flex-1 min-w-[80px] bg-red-600 hover:bg-red-700 text-white px-3 py-2 rounded text-sm"
        >
          Dismiss
        </Button>
        <Button
          onClick={() => {
            void navigator.clipboard.writeText(JSON.stringify(session, null, 2));
          }}
          className="h-8 flex-1 min-w-[80px] bg-slate-700 hover:bg-slate-600 text-white px-3 py-2 rounded text-sm"
        >
          Copy JSON
        </Button>
        {session.id && fp && (
          <a
            href={fingerprintExportUrl(session.id)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-8 flex-1 min-w-[80px] items-center justify-center rounded bg-cyan-700 px-3 text-sm text-white hover:bg-cyan-600"
          >
            Export FP
          </a>
        )}
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm font-medium text-white">{value}</p>
    </div>
  );
}
