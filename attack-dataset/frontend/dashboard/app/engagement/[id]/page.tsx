"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import TerminalOutput from "@/components/attack-monitoring/TerminalOutput";
import { analyzerHttp, orchestratorFetchInit, orchestratorHttp, orchestratorWs } from "@/lib/config";
import {
  executeAttackChain as postExecuteChain,
  formatExecuteChainError,
  startFullEngagementFromOpsec,
} from "@/lib/orchestratorClient";
import CouncilTimeline from "@/components/attack-monitoring/CouncilTimeline";
import {
  appendCouncilEvent,
  isCouncilWsMessage,
  type CouncilWsEvent,
  type LiveCouncilState,
} from "@/lib/liveCouncil";

interface EngagementData {
  id: string;
  target: string;
  status: string;
  started_at: string;
  completed_at?: string;
  scan_session?: any;
  attack_chains?: { version?: number; chains?: unknown[] };
  opsec_reports?: any;
  opsec_audit?: any;
  ai_summary?: string;
  analysis_overseer?: any;
  log?: Array<{ ts: string; msg: string }>;
  chain_execution?: any;
  live_council?: LiveCouncilState;
  reasoning_trace?: Array<Record<string, unknown>>;
  source?: string;
}

interface ScanSession {
  id: string;
  target: string;
  status: string;
  fingerprint?: {
    target: string;
    ip: string;
    os: string;
    services: Array<{
      port: string;
      protocol: string;
      name: string;
      product: string;
      version: string;
    }>;
  };
  started_at: string;
  error?: string;
}

function StatusPill({ status }: { status: string }) {
  const configs: Record<string, { bg: string; text: string; dot: string; label: string }> = {
    complete: { bg: "bg-emerald-500/10", text: "text-emerald-400", dot: "bg-emerald-400", label: "Completed" },
    completed: { bg: "bg-emerald-500/10", text: "text-emerald-400", dot: "bg-emerald-400", label: "Completed" },
    error: { bg: "bg-red-500/10", text: "text-red-400", dot: "bg-red-400", label: "Error" },
    starting: { bg: "bg-amber-500/10", text: "text-amber-400", dot: "bg-amber-400 animate-pulse", label: "Starting" },
    running: { bg: "bg-cyan-500/10", text: "text-cyan-400", dot: "bg-cyan-400 animate-pulse", label: "Running" },
  };
  const c = configs[status] || { bg: "bg-slate-700/30", text: "text-slate-400", dot: "bg-slate-400", label: status };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${c.bg} ${c.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}

function SectionCard({ title, live, children }: { title: string; live?: boolean; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-base font-semibold text-white">{title}</h2>
        {live && <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />}
      </div>
      {children}
    </section>
  );
}

export default function EngagementDetails() {
  const params = useParams();
  const router = useRouter();
  const engagementId = params.id as string;

  const [engagement, setEngagement] = useState<EngagementData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionStatus, setExecutionStatus] = useState<string>("");
  const [selectedChain, setSelectedChain] = useState<number>(0);
  const [scanSessions, setScanSessions] = useState<ScanSession[]>([]);
  const [liveScanData, setLiveScanData] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [councilWsEvents, setCouncilWsEvents] = useState<CouncilWsEvent[]>([]);
  const [liveCouncilEnabling, setLiveCouncilEnabling] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchEngagementDetails();
    connectWebSocket();
    startScanPolling();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    };
  }, [engagementId]);

  const fetchEngagementDetails = async () => {
    try {
      setLoading(true);
      const response = await fetch(orchestratorHttp(`/engagements/${engagementId}`), orchestratorFetchInit());
      if (!response.ok) throw new Error(`Failed: ${response.statusText}`);
      setEngagement(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  const enableLiveCouncil = async () => {
    setLiveCouncilEnabling(true);
    try {
      const res = await fetch(
        orchestratorHttp(`/engagements/${engagementId}/live/enable`),
        orchestratorFetchInit({ method: "POST" })
      );
      if (res.ok) {
        const data = await res.json();
        setEngagement((prev) =>
          prev ? { ...prev, live_council: data.live_council } : prev
        );
      }
    } finally {
      setLiveCouncilEnabling(false);
    }
  };

  const executeAttackChain = async (chainIndex: number) => {
    if (!engagement) return;
    setIsExecuting(true);
    setExecutionStatus("Initializing...");
    setSelectedChain(chainIndex);
    try {
      const chain = engagement.attack_chains?.chains?.[chainIndex];
      const result = await postExecuteChain({
        engagement_id: engagement.id,
        chain_index: chainIndex,
        chain,
      });
      if (result.ok) {
        const data = result.data as { success?: boolean };
        setExecutionStatus(data.success ? "Executed successfully" : "Execution failed");
        setTimeout(() => fetchEngagementDetails(), 2000);
      } else {
        setExecutionStatus(formatExecuteChainError(result.body));
      }
    } catch {
      setExecutionStatus("Error executing");
    } finally {
      setIsExecuting(false);
    }
  };

  const connectWebSocket = () => {
    try {
      const ws = new WebSocket(`${orchestratorWs("/")}?engagement=${engagementId}`);
      ws.onopen = () => setIsConnected(true);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (isCouncilWsMessage(data)) {
            setCouncilWsEvents((prev) => appendCouncilEvent(prev, data));
            if (data.type === "live_directive") {
              setEngagement((prev) =>
                prev
                  ? {
                      ...prev,
                      live_council: {
                        ...prev.live_council,
                        enabled: true,
                        last_directive: data.directive,
                        turn: data.directive.turn ?? prev.live_council?.turn,
                      },
                    }
                  : null
              );
            }
            return;
          }
          if (data.id || data.target) {
            setEngagement(data);
            if (data.scan_session) setLiveScanData(data.scan_session);
          } else if (!(data.type === "info" || data.type === "connection")) {
            setEngagement((prev) => (prev ? { ...prev, ...data } : null));
          }
        } catch {}
      };
      ws.onerror = () => setIsConnected(false);
      ws.onclose = () => {
        setIsConnected(false);
        setTimeout(() => { if (wsRef.current?.readyState === WebSocket.CLOSED) connectWebSocket(); }, 5000);
      };
      wsRef.current = ws;
    } catch {}
  };

  const startScanPolling = () => {
    const poll = async () => {
      try {
        const res = await fetch(analyzerHttp("/sessions"));
        if (res.ok) {
          const sessions = await res.json();
          if (engagement) {
            const filtered = sessions.filter((s: ScanSession) => s.target === engagement.target);
            setScanSessions(filtered);
            if (filtered.length > 0) setLiveScanData(filtered[filtered.length - 1]);
          }
        }
      } catch {}
    };
    poll();
    pollingIntervalRef.current = setInterval(poll, 3000);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#080c14] text-white">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-cyan-500" />
          <p className="text-sm text-slate-400">Loading engagement...</p>
        </div>
      </div>
    );
  }

  if (error || !engagement) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#080c14] text-white">
        <div className="text-center">
          <div className="mb-3 text-3xl">❌</div>
          <h2 className="mb-1 text-lg font-semibold">Error</h2>
          <p className="mb-4 text-sm text-slate-400">{error || "Not found"}</p>
          <Button onClick={() => router.back()} size="sm" className="bg-cyan-600 hover:bg-cyan-500">
            Go Back
          </Button>
        </div>
      </div>
    );
  }

  const services = liveScanData?.fingerprint?.services || engagement.scan_session?.fingerprint?.services || [];

  return (
    <div className="min-h-screen bg-[#080c14] text-white">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-slate-800/60 bg-[#080c14]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Button onClick={() => router.back()} variant="ghost" size="sm" className="h-8 text-slate-400 hover:text-white">
              ← Back
            </Button>
            <div>
              <h1 className="text-lg font-bold text-white">Engagement Results</h1>
              <p className="text-xs text-slate-500">{engagement.target} · {engagement.id}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {engagement.status === 'complete' && engagement.attack_chains?.chains && (
              <Button
                onClick={() => router.push(`/operations?engagement=${engagement.id}`)}
                size="sm"
                className="h-8 bg-gradient-to-r from-cyan-600 to-blue-600 text-white hover:from-cyan-500 hover:to-blue-500"
              >
                Execute Chains
              </Button>
            )}
            <StatusPill status={engagement.status} />
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${isConnected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-700/30 text-slate-400'}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400'}`} />
              {isConnected ? 'Live' : 'Offline'}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8 space-y-6">
        {engagement.source === "opsec_assessment" && (
          <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 px-4 py-3 text-sm text-slate-300">
            <p className="font-medium text-cyan-300">OpSec assessment engagement</p>
            <p className="mt-1 text-xs text-slate-400">
              Chains are scored and ready. Use Execute Chains for Jailbreak-guided steps, or start a full engagement to run live scanning while keeping these chains.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                className="h-8 bg-cyan-600 hover:bg-cyan-500"
                onClick={() => router.push(`/operations?engagement=${engagement.id}`)}
              >
                Execute Chains
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-8 border-slate-600"
                onClick={async () => {
                  const result = await startFullEngagementFromOpsec(engagement.id);
                  if (result.ok) router.push(`/engagement/${result.data.engagement_id}`);
                }}
              >
                Start Full Engagement
              </Button>
            </div>
          </div>
        )}

        {/* Overview */}
        <SectionCard title="Overview">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-4">
              <p className="mb-1 text-xs text-slate-500">Target</p>
              <p className="font-medium text-sm">{engagement.target}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-4">
              <p className="mb-1 text-xs text-slate-500">Started</p>
              <p className="font-medium text-sm">{new Date(engagement.started_at).toLocaleString()}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-4">
              <p className="mb-1 text-xs text-slate-500">Completed</p>
              <p className="font-medium text-sm">{engagement.completed_at ? new Date(engagement.completed_at).toLocaleString() : 'In Progress'}</p>
            </div>
          </div>
        </SectionCard>

        {/* Scan Results */}
        {(engagement.scan_session || liveScanData || scanSessions.length > 0) && (
          <SectionCard title="Scan Results" live={!!liveScanData}>
            {liveScanData && (
              <div className="mb-5 rounded-lg border border-cyan-500/10 bg-cyan-950/20 p-4">
                <div className="mb-3 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
                  <span className="text-sm font-medium text-cyan-300">Live Scan Session</span>
                  <StatusPill status={liveScanData.status} />
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <div>
                    <p className="text-xs text-slate-500">ID</p>
                    <p className="font-mono text-xs text-slate-300">{liveScanData.id?.split('-')[1] || liveScanData.id}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Target</p>
                    <p className="text-slate-300">{liveScanData.target}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">IP</p>
                    <p className="text-slate-300">{liveScanData.fingerprint?.ip || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Started</p>
                    <p className="text-slate-300">{new Date(liveScanData.started_at).toLocaleTimeString()}</p>
                  </div>
                </div>
                {liveScanData.error && (
                  <div className="mt-3 rounded bg-red-500/10 px-3 py-2 text-xs text-red-400">{liveScanData.error}</div>
                )}
              </div>
            )}

            {services.length > 0 && (
              <div>
                <p className="mb-3 text-xs text-slate-500">Detected Services ({services.length})</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {services.map((service: any, idx: number) => (
                    <div key={idx} className="group rounded-lg border border-slate-800 bg-slate-950/30 p-3 transition-colors hover:border-cyan-500/30">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-cyan-300">{service.name || 'Unknown'}</span>
                        <span className="text-[10px] text-slate-600">{service.port}/{service.protocol}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{service.product} {service.version}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {scanSessions.length > 1 && (
              <div className="mt-5">
                <p className="mb-2 text-xs text-slate-500">All Sessions</p>
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {scanSessions.map((session, idx) => (
                    <div key={idx} className={`flex items-center justify-between rounded-lg px-3 py-2 text-xs ${session.id === liveScanData?.id ? 'border border-cyan-500/20 bg-cyan-950/10' : 'bg-slate-950/30'}`}>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-slate-500">{session.id?.split('-')[1] || session.id}</span>
                        <StatusPill status={session.status} />
                      </div>
                      <span className="text-slate-600">{session.fingerprint?.services?.length || 0} svc</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </SectionCard>
        )}

        {/* Live Attack Council */}
        {(engagement.live_council?.enabled ||
          engagement.chain_execution ||
          councilWsEvents.length > 0) && (
          <SectionCard title="Live Attack Council" live={isConnected}>
            {!engagement.live_council?.enabled && (
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <p className="text-xs text-slate-500">
                  Enable the council to replan chains from dataset + ML when steps fail during execution.
                </p>
                <Button
                  size="sm"
                  onClick={enableLiveCouncil}
                  disabled={liveCouncilEnabling}
                  className="h-7 bg-purple-600 text-xs hover:bg-purple-500"
                >
                  {liveCouncilEnabling ? "Enabling…" : "Enable live council"}
                </Button>
              </div>
            )}
            <CouncilTimeline
              liveCouncil={engagement.live_council}
              wsEvents={councilWsEvents}
              chainsVersion={engagement.attack_chains?.version}
            />
          </SectionCard>
        )}

        {/* Attack Chains */}
        {engagement.attack_chains?.chains && (
          <SectionCard title={`Attack Chains (${engagement.attack_chains.chains.length})`}>
            <div className="space-y-4">
              {engagement.attack_chains.chains.map((chain: any, idx: number) => (
                <div key={idx} className="rounded-lg border border-slate-800 bg-slate-950/30 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="flex h-6 w-6 items-center justify-center rounded-md bg-cyan-500/10 text-xs font-bold text-cyan-400">{idx + 1}</span>
                      <span className="text-sm font-medium text-slate-200">Chain {idx + 1}</span>
                      <span className="text-xs text-slate-500">{Math.round((chain.confidence || 0) * 100)}% confidence</span>
                    </div>
                    {engagement.status === 'complete' && (
                      <Button
                        onClick={() => executeAttackChain(idx)}
                        disabled={isExecuting}
                        size="sm"
                        className="h-7 bg-gradient-to-r from-cyan-600 to-blue-600 text-xs text-white hover:from-cyan-500 hover:to-blue-500"
                      >
                        {isExecuting && selectedChain === idx ? "Executing..." : "Execute"}
                      </Button>
                    )}
                  </div>
                  <div className="space-y-2">
                    {chain.steps?.map((step: any, sIdx: number) => {
                      // Defensive: backend may return attack as a string (old format) or object (new format)
                      const s = step as any;
                      const attackTitle = typeof s.attack === 'string'
                        ? s.attack
                        : s.attack?.title || s.attack || s.phase || 'Unknown step';
                      const attackMitre = typeof s.attack === 'string'
                        ? s.mitre_technique
                        : s.attack?.mitre_technique;
                      const stepPhase = s.phase || 'Unknown phase';
                      return (
                        <div key={sIdx} className="flex items-start gap-2 text-sm">
                          <span className="mt-0.5 text-[10px] text-slate-600">{sIdx + 1}.</span>
                          <div>
                            <p className="font-medium text-slate-300">{attackTitle}</p>
                            {stepPhase !== 'Unknown phase' && (
                              <p className="text-xs text-slate-500">{stepPhase}</p>
                            )}
                            {attackMitre && (
                              <span className="mt-1 inline-block rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] text-purple-400">{attackMitre}</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>
        )}

        {/* Execution Status */}
        {executionStatus && (
          <SectionCard title="Execution Status">
            <div className={`rounded-lg px-4 py-3 text-sm ${executionStatus.includes("success") ? "border border-emerald-500/20 bg-emerald-950/20 text-emerald-400" : executionStatus.includes("failed") || executionStatus.includes("Error") ? "border border-red-500/20 bg-red-950/20 text-red-400" : "border border-slate-700 bg-slate-950/30 text-slate-300"}`}>
              {executionStatus}
            </div>
          </SectionCard>
        )}

        {/* Chain Execution Results */}
        {engagement.chain_execution && (
          <SectionCard title="Chain Execution Results">
            <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { label: "Status", value: engagement.chain_execution.status, color: engagement.chain_execution.status === 'completed' ? 'text-emerald-400' : engagement.chain_execution.status === 'running' ? 'text-amber-400' : 'text-red-400' },
                { label: "Execution ID", value: engagement.chain_execution.execution_id },
                { label: "Progress", value: `${engagement.chain_execution.current_step}/${engagement.chain_execution.total_steps}` },
                { label: "Method", value: engagement.chain_execution.jailbreak_enhanced ? 'Jailbreak AI' : 'Standard', color: engagement.chain_execution.jailbreak_enhanced ? 'text-purple-400' : '' },
              ].map((item) => (
                <div key={item.label} className="rounded-lg border border-slate-800 bg-slate-950/30 p-3">
                  <p className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">{item.label}</p>
                  <p className={`text-sm font-medium ${item.color || 'text-slate-200'}`}>{item.value}</p>
                </div>
              ))}
            </div>
            {engagement.chain_execution.steps?.length > 0 && (
              <div className="space-y-2">
                {engagement.chain_execution.steps.map((step: any, idx: number) => (
                  <div key={idx} className={`rounded-lg border-l-2 p-3 ${step.status === 'success' ? 'border-emerald-500 bg-emerald-950/10' : step.status === 'failed' ? 'border-red-500 bg-red-950/10' : 'border-amber-500 bg-amber-950/10'}`}>
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-sm font-medium">Step {step.step_number}</span>
                      <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${step.status === 'success' ? 'bg-emerald-500/10 text-emerald-400' : step.status === 'failed' ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'}`}>{step.status}</span>
                    </div>
                    {step.jailbreak_guidance && (
                      <div className="mb-2 rounded bg-purple-500/10 px-2 py-1.5 text-xs text-purple-300">{step.jailbreak_guidance.substring(0, 120)}...</div>
                    )}
                    <p className="truncate text-xs font-mono text-slate-500">{step.output?.substring(0, 200)}...</p>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        )}

        {/* OpSec */}
        {engagement.opsec_reports && (
          <SectionCard title="OpSec Assessment">
            <div className="mb-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs text-slate-500">Risk Score</span>
                <span className="text-sm font-medium text-slate-200">{engagement.opsec_reports.risk_score || 0}/100</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                <div className="h-full rounded-full bg-gradient-to-r from-amber-500 to-red-500 transition-all" style={{ width: `${engagement.opsec_reports.risk_score || 0}%` }} />
              </div>
            </div>
            {engagement.opsec_reports.findings?.map((finding: any, idx: number) => (
              <div key={idx} className="mb-2 rounded-lg border border-red-500/10 bg-red-950/10 p-3">
                <span className="mb-1 inline-block rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] font-medium text-red-400">{finding.severity}</span>
                <p className="text-sm text-slate-300">{finding.description}</p>
              </div>
            ))}
          </SectionCard>
        )}

        {/* AI Summary */}
        {engagement.ai_summary && (
          <SectionCard title="AI Intelligence Summary">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{engagement.ai_summary}</p>
          </SectionCard>
        )}

        {/* Quality */}
        {engagement.analysis_overseer?.quality && (
          <SectionCard title="Quality Metrics">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
              {Object.entries(engagement.analysis_overseer.quality).map(([key, value]) => (
                <div key={key} className="rounded-lg border border-slate-800 bg-slate-950/30 p-4 text-center">
                  <p className="text-xl font-bold text-cyan-400">{Math.round(value as number)}%</p>
                  <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-500">{key.replace(/_/g, ' ')}</p>
                </div>
              ))}
            </div>
          </SectionCard>
        )}

        {/* Log */}
        {engagement.log && engagement.log.length > 0 && (
          <SectionCard title="Execution Log" live={isConnected}>
            <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/50 p-3">
              {engagement.log.map((entry, idx) => (
                <div key={idx} className="mb-1 flex gap-2 text-xs font-mono">
                  <span className="shrink-0 text-slate-600">[{new Date(entry.ts).toLocaleTimeString()}]</span>
                  <span className="text-slate-400">{entry.msg}</span>
                </div>
              ))}
            </div>
          </SectionCard>
        )}

        {/* Activity Feed */}
        <SectionCard title="Activity Feed" live={isConnected}>
          <div className="space-y-2">
            {liveScanData && (
              <div className="flex items-start gap-3 rounded-lg bg-slate-950/30 p-3 text-sm">
                <span className="mt-0.5 text-cyan-400">🔍</span>
                <div>
                  <p className="font-medium text-slate-200">Scan Activity</p>
                  <p className="text-xs text-slate-500">{liveScanData.target} · {liveScanData.status} · {liveScanData.fingerprint?.services?.length || 0} services</p>
                </div>
              </div>
            )}
            {scanSessions.length > 0 && (
              <div className="flex items-start gap-3 rounded-lg bg-slate-950/30 p-3 text-sm">
                <span className="mt-0.5 text-purple-400">📊</span>
                <div>
                  <p className="font-medium text-slate-200">Sessions Available</p>
                  <p className="text-xs text-slate-500">{scanSessions.length} sessions · Latest: {scanSessions[scanSessions.length - 1]?.status}</p>
                </div>
              </div>
            )}
            {engagement.status === 'starting' && (
              <div className="flex items-start gap-3 rounded-lg border border-amber-500/10 bg-amber-950/10 p-3 text-sm">
                <span className="mt-0.5 text-amber-400">⏳</span>
                <div>
                  <p className="font-medium text-slate-200">Engagement Starting</p>
                  <p className="text-xs text-slate-500">Initializing scan pipeline for {engagement.target}...</p>
                </div>
              </div>
            )}
            {engagement.status === 'complete' && (
              <div className="flex items-start gap-3 rounded-lg border border-emerald-500/10 bg-emerald-950/10 p-3 text-sm">
                <span className="mt-0.5 text-emerald-400">✅</span>
                <div>
                  <p className="font-medium text-slate-200">Engagement Complete</p>
                  <p className="text-xs text-slate-500">Analysis finished for {engagement.target}</p>
                </div>
              </div>
            )}
            {!liveScanData && scanSessions.length === 0 && engagement.status === 'starting' && (
              <div className="flex items-start gap-3 rounded-lg bg-slate-950/30 p-3 text-sm">
                <span className="mt-0.5 text-slate-500">⚡</span>
                <div>
                  <p className="font-medium text-slate-200">Waiting for Scan Data</p>
                  <p className="text-xs text-slate-500">No scan sessions detected yet. Polling realtime analyzer...</p>
                </div>
              </div>
            )}
          </div>
        </SectionCard>

        {/* Live Terminal */}
        {(engagement.status === 'starting' || engagement.status === 'running' || engagement.chain_execution) && (
          <SectionCard title="Live Terminal" live={isConnected}>
            <TerminalOutput
              engagementId={engagement.id}
              isActive={engagement.status === 'running' || engagement.status === 'starting' || !!engagement.chain_execution}
              councilEvents={councilWsEvents}
              reasoningTrace={engagement.reasoning_trace}
            />
          </SectionCard>
        )}
      </main>
    </div>
  );
}
