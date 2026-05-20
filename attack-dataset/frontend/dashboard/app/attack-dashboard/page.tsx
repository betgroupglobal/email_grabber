"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { OperationsCenter } from "@/components/attack-monitoring/OperationsCenter";
import { Button } from "@/components/ui/button";
import TerminalOutput from "@/components/attack-monitoring/TerminalOutput";
import RealTimeAttackMonitor from "@/components/attack-monitoring/RealTimeAttackMonitor";
import { orchestratorFetchInit, orchestratorHttp } from "@/lib/config";
import {
  executeAttackChain as postExecuteChain,
  formatExecuteChainError,
  startFullEngagementFromOpsec,
} from "@/lib/orchestratorClient";
import CouncilTimeline from "@/components/attack-monitoring/CouncilTimeline";
import { orchestratorWs } from "@/lib/config";
import {
  appendCouncilEvent,
  isCouncilWsMessage,
  type CouncilWsEvent,
  type LiveCouncilState,
} from "@/lib/liveCouncil";

interface Engagement {
  id: string;
  target: string;
  status: string;
  started_at: string;
  source?: string;
  attack_chains?: {
    version?: number;
    chains: Array<{
      steps: Array<{
        attack: AttackDescriptor;
        phase: string;
        mitre_technique?: string;
        description?: string;
        command?: string;
      }>;
      confidence: number;
    }>;
  };
  live_council?: LiveCouncilState;
  reasoning_trace?: Array<Record<string, unknown>>;
  chain_execution?: {
    execution_id: string;
    status: string;
    current_step: number;
    total_steps: number;
    steps: Array<{
      step_number: number;
      status: string;
      output: string;
      jailbreak_guidance?: string;
    }>;
  };
}

type AttackDescriptor = string | {
  title?: string;
  mitre_technique?: string;
  description?: string;
  command?: string;
};

type AttackStep = {
  attack: AttackDescriptor;
  phase?: string;
  mitre_technique?: string;
  description?: string;
  command?: string;
};

const phaseStyles: Record<string, { label: string; color: string; bar: string; dot: string }> = {
  reconnaissance: { label: "Reconnaissance", color: "text-sky-300", bar: "bg-sky-500", dot: "bg-sky-400" },
  scanning: { label: "Scanning", color: "text-cyan-300", bar: "bg-cyan-500", dot: "bg-cyan-400" },
  exploitation: { label: "Exploitation", color: "text-amber-300", bar: "bg-amber-500", dot: "bg-amber-400" },
  privilege_escalation: { label: "Privilege Escalation", color: "text-orange-300", bar: "bg-orange-500", dot: "bg-orange-400" },
  persistence: { label: "Persistence", color: "text-fuchsia-300", bar: "bg-fuchsia-500", dot: "bg-fuchsia-400" },
  lateral_movement: { label: "Lateral Movement", color: "text-violet-300", bar: "bg-violet-500", dot: "bg-violet-400" },
  exfiltration: { label: "Exfiltration", color: "text-red-300", bar: "bg-red-500", dot: "bg-red-400" },
  cleanup: { label: "Cleanup", color: "text-emerald-300", bar: "bg-emerald-500", dot: "bg-emerald-400" },
  unknown_phase: { label: "Unknown Phase", color: "text-slate-300", bar: "bg-slate-500", dot: "bg-slate-400" },
};

const normalizePhase = (phase?: string) => (phase || "unknown_phase").toLowerCase().replace(/[\s-]+/g, "_");

const getPhaseStyle = (phase?: string) => {
  const key = normalizePhase(phase);
  return phaseStyles[key] || {
    label: (phase || "Unknown Phase").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    color: "text-slate-300",
    bar: "bg-slate-500",
    dot: "bg-slate-400",
  };
};

const getStepDetails = (step: AttackStep) => {
  const attackTitle = typeof step.attack === 'string'
    ? step.attack
    : step.attack.title || step.phase || 'Unknown step';
  const attackMitre = typeof step.attack === 'string'
    ? step.mitre_technique
    : step.attack.mitre_technique || step.mitre_technique;
  const phase = step.phase || 'Unknown phase';
  return { attackTitle, attackMitre, phase, phaseStyle: getPhaseStyle(phase) };
};

function StepBadge({ status }: { status: string }) {
  const configs: Record<string, { bg: string; text: string; label: string }> = {
    success: { bg: "bg-emerald-500/10", text: "text-emerald-400", label: "Success" },
    failed: { bg: "bg-red-500/10", text: "text-red-400", label: "Failed" },
    running: { bg: "bg-amber-500/10", text: "text-amber-400", label: "Running" },
    pending: { bg: "bg-slate-700/30", text: "text-slate-400", label: "Pending" },
  };
  const c = configs[status] || configs.pending;
  return (
    <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}

function PhaseOverview({ steps }: { steps: AttackStep[] }) {
  const phases = steps.reduce<Record<string, { label: string; count: number; style: ReturnType<typeof getPhaseStyle> }>>((acc, step) => {
    const { phase, phaseStyle } = getStepDetails(step);
    const key = normalizePhase(phase);
    acc[key] = acc[key] || { label: phaseStyle.label, count: 0, style: phaseStyle };
    acc[key].count += 1;
    return acc;
  }, {});
  const items = Object.values(phases);

  return (
    <div className="mb-5 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Attack phase map</p>
          <p className="text-[11px] text-slate-600">{items.length} phases across {steps.length} steps</p>
        </div>
        <span className="rounded-full bg-cyan-500/10 px-2 py-1 text-[10px] text-cyan-300">Live chain context</span>
      </div>
      <div className="flex overflow-hidden rounded-full bg-slate-800">
        {items.map((item) => (
          <div
            key={item.label}
            className={`h-2 ${item.style.bar}`}
            style={{ width: `${(item.count / steps.length) * 100}%` }}
            title={`${item.label}: ${item.count}`}
          />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.map((item) => (
          <span key={item.label} className="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/70 px-2 py-1 text-[10px] text-slate-300">
            <span className={`h-1.5 w-1.5 rounded-full ${item.style.dot}`} />
            <span className={item.style.color}>{item.label}</span>
            <span className="text-slate-600">×{item.count}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function Panel({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm ${className}`}>
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
      {children}
    </div>
  );
}

type DashboardView = "execution" | "operations";

function AttackDashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const view: DashboardView =
    searchParams.get("view") === "operations" ? "operations" : "execution";
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selected, setSelected] = useState<Engagement | null>(null);
  const [chainIdx, setChainIdx] = useState(0);
  const [executing, setExecuting] = useState(false);
  const [execStatus, setExecStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [terminalActive, setTerminalActive] = useState(false);
  const [councilWsEvents, setCouncilWsEvents] = useState<CouncilWsEvent[]>([]);
  const councilWsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!selected?.id) {
      councilWsRef.current?.close();
      councilWsRef.current = null;
      return;
    }
    const ws = new WebSocket(`${orchestratorWs("/")}?engagement=${selected.id}`);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (isCouncilWsMessage(data)) {
          setCouncilWsEvents((prev) => appendCouncilEvent(prev, data));
          if (data.type === "live_directive") {
            setSelected((prev) =>
              prev
                ? {
                    ...prev,
                    live_council: {
                      ...prev.live_council,
                      enabled: true,
                      last_directive: data.directive,
                    },
                  }
                : null
            );
          }
        } else if (data.id && data.target) {
          setSelected(data);
          setEngagements((prev) => prev.map((e) => (e.id === data.id ? data : e)));
        }
      } catch {}
    };
    councilWsRef.current = ws;
    return () => {
      ws.close();
      councilWsRef.current = null;
    };
  }, [selected?.id]);

  async function fetchEngagements() {
    try {
      const res = await fetch(orchestratorHttp("/engagements"), orchestratorFetchInit());
      if (res.ok) {
        const data = await res.json();
        const completed = data.filter(
          (e: Engagement) => e.status === "complete" && e.attack_chains?.chains
        );
        setEngagements(completed);
      }
    } catch {
      setEngagements([]);
    }
    setLoading(false);
  }

  useEffect(() => {
    const initialLoad = window.setTimeout(fetchEngagements, 0);
    const interval = setInterval(fetchEngagements, 5000);
    return () => {
      window.clearTimeout(initialLoad);
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const preselect = new URLSearchParams(window.location.search).get("engagement");
    if (!preselect || selected?.id === preselect) return;
    fetch(orchestratorHttp(`/engagements/${preselect}`), orchestratorFetchInit())
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setSelected(data);
          setChainIdx(0);
        }
      })
      .catch(() => {});
  }, [selected?.id]);

  const fetchDetails = async (id: string) => {
    try {
      const res = await fetch(orchestratorHttp(`/engagements/${id}`), orchestratorFetchInit());
      if (res.ok) {
        const data = await res.json();
        setSelected(data);
        setEngagements((prev) => prev.map((e) => (e.id === id ? data : e)));
      }
    } catch {}
  };

  const startFullEngagement = async () => {
    if (!selected) return;
    setExecuting(true);
    setExecStatus("Starting full engagement pipeline...");
    try {
      const result = await startFullEngagementFromOpsec(selected.id);
      if (result.ok) {
        const newId = result.data.engagement_id;
        setExecStatus(`Full engagement ${newId} started — opening...`);
        router.push(`/engagement/${newId}`);
      } else {
        setExecStatus(
          String(result.body.error || `Failed to start full engagement (${result.status})`)
        );
      }
    } catch {
      setExecStatus("Error starting full engagement");
    } finally {
      setExecuting(false);
    }
  };

  const executeChain = async () => {
    if (!selected) return;
    setExecuting(true);
    setExecStatus("Initializing...");
    setTerminalActive(true);
    try {
      const chain = selected.attack_chains?.chains?.[chainIdx];
      if (!chain) {
        setExecStatus("No chain selected");
        return;
      }
      const result = await postExecuteChain({
        engagement_id: selected.id,
        chain_index: chainIdx,
        chain,
      });
      if (result.ok) {
        const data = result.data as { success?: boolean };
        setExecStatus(data.success ? "Executed successfully" : "Execution failed");
        setTimeout(() => fetchDetails(selected.id), 2000);
      } else {
        setExecStatus(formatExecuteChainError(result.body));
      }
    } catch {
      setExecStatus("Error executing");
    } finally {
      setExecuting(false);
    }
  };

  const stopExecution = async () => {
    if (!selected?.chain_execution?.execution_id) return;
    try {
      await fetch(orchestratorHttp("/stop-execution"), orchestratorFetchInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ execution_id: selected.chain_execution.execution_id }),
      }));
      setExecStatus("Stopped");
      setExecuting(false);
    } catch {}
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#080c14] text-white">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-cyan-500" />
          <p className="text-sm text-slate-400">Loading attack dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#080c14] text-white">
      <header className="sticky top-0 z-40 border-b border-slate-800/60 bg-[#080c14]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 text-lg shadow-lg shadow-cyan-500/20">
              🎯
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Attack Execution</h1>
              <p className="text-[11px] text-slate-500">AI-guided execution with real-time monitoring</p>
            </div>
          </div>
          <Button onClick={() => router.push("/")} size="sm" variant="ghost" className="h-8 text-slate-400 hover:text-white">
            ← Back
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6 flex gap-2 rounded-lg border border-slate-800 bg-slate-900/50 p-1">
          {(
            [
              { id: "execution" as const, label: "Chain execution" },
              { id: "operations" as const, label: "Operations center" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                const params = new URLSearchParams(searchParams.toString());
                if (tab.id === "execution") params.delete("view");
                else params.set("view", tab.id);
                const q = params.toString();
                router.replace(q ? `/attack-dashboard?${q}` : "/attack-dashboard");
              }}
              className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-all ${
                view === tab.id
                  ? "bg-cyan-600 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {view === "operations" ? (
          <OperationsCenter engagementId={selected?.id} />
        ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Left */}
          <div className="space-y-5">
            <Panel title="Engagements">
              {engagements.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-800 py-10 text-center">
                  <p className="text-sm text-slate-500">No completed engagements</p>
                  <p className="mt-1 text-xs text-slate-600">Complete an engagement to execute chains</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {engagements.map((e) => (
                    <button
                      key={e.id}
                      onClick={() => { setSelected(e); setChainIdx(0); setTerminalActive(false); }}
                      className={`w-full rounded-lg border p-3 text-left transition-all ${
                        selected?.id === e.id
                          ? "border-cyan-500/30 bg-cyan-950/20"
                          : "border-slate-800 bg-slate-950/30 hover:border-slate-700 hover:bg-slate-900/50"
                      }`}
                    >
                      <p className="text-sm font-medium text-slate-200">{e.target}</p>
                      <p className="text-[10px] text-slate-500">
                        {e.attack_chains?.chains.length || 0} chains{e.source === "opsec_assessment" ? " · OpSec assessment" : ""}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </Panel>

            {selected && (
              <Panel title="Chains">
                <div className="space-y-2">
                  {selected.attack_chains?.chains.map((chain, idx) => (
                    <button
                      key={idx}
                      onClick={() => setChainIdx(idx)}
                      className={`w-full rounded-lg border p-3 text-left transition-all ${
                        chainIdx === idx
                          ? "border-cyan-500/30 bg-cyan-950/20"
                          : "border-slate-800 bg-slate-950/30 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-200">Chain {idx + 1}</span>
                        <span className="text-[10px] text-slate-500">{Math.round(chain.confidence * 100)}%</span>
                      </div>
                      <p className="text-[10px] text-slate-500">{chain.steps.length} steps</p>
                    </button>
                  ))}
                </div>
              </Panel>
            )}

            {selected && (
              <Panel title="Controls">
                {selected.chain_execution ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-2">
                      <span className="text-xs text-slate-500">Status</span>
                      <StepBadge status={selected.chain_execution.status} />
                    </div>
                    <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-3">
                      <div className="mb-2 flex items-center justify-between text-xs">
                        <span className="text-slate-500">Progress</span>
                        <span className="text-slate-300">{selected.chain_execution.current_step}/{selected.chain_execution.total_steps}</span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all"
                          style={{ width: `${(selected.chain_execution.current_step / selected.chain_execution.total_steps) * 100}%` }}
                        />
                      </div>
                    </div>
                    {selected.chain_execution.status === 'running' && (
                      <Button onClick={stopExecution} size="sm" className="w-full h-8 bg-red-600 text-xs text-white hover:bg-red-500">
                        Stop Execution
                      </Button>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {selected.source === "opsec_assessment" && (
                      <p className="text-[11px] text-slate-500 leading-relaxed">
                        OpSec assessment chains are ready. Execute here with Jailbreak AI, or start a full engagement to add live scanning and enrichment.
                      </p>
                    )}
                    <Button
                      onClick={executeChain}
                      disabled={executing}
                      className="h-9 w-full bg-gradient-to-r from-cyan-600 to-blue-600 text-sm font-medium text-white hover:from-cyan-500 hover:to-blue-500 hover:shadow-lg hover:shadow-cyan-500/20"
                    >
                      {executing ? "Executing..." : "Execute Chain"}
                    </Button>
                    {selected.source === "opsec_assessment" && (
                      <Button
                        onClick={startFullEngagement}
                        disabled={executing}
                        variant="outline"
                        className="h-9 w-full border-slate-600 bg-slate-900/50 text-sm text-slate-200 hover:bg-slate-800"
                      >
                        Start Full Engagement
                      </Button>
                    )}
                    {execStatus && (
                      <div className={`rounded-lg border px-3 py-2 text-xs ${execStatus.includes("success") ? "border-emerald-500/20 bg-emerald-950/20 text-emerald-400" : execStatus.includes("failed") || execStatus.includes("Error") ? "border-red-500/20 bg-red-950/20 text-red-400" : "border-slate-700 bg-slate-950/30 text-slate-300"}`}>
                        {execStatus}
                      </div>
                    )}
                  </div>
                )}
              </Panel>
            )}
          </div>

          {/* Right */}
          <div className="lg:col-span-2 space-y-5">
            {selected && selected.attack_chains?.chains[chainIdx] && (
              <Panel title={`Chain ${chainIdx + 1} Steps`}>
                <PhaseOverview steps={selected.attack_chains.chains[chainIdx].steps as AttackStep[]} />
                <div className="space-y-3">
                  {selected.attack_chains.chains[chainIdx].steps.map((step, idx) => {
                    const execStep = selected.chain_execution?.steps[idx];
                    const { attackTitle, attackMitre, phase, phaseStyle } = getStepDetails(step as AttackStep);
                    return (
                      <div
                        key={idx}
                        className={`relative overflow-hidden rounded-lg border-l-2 p-4 ${
                          execStep?.status === 'success' ? 'border-emerald-500 bg-emerald-950/10' :
                          execStep?.status === 'failed' ? 'border-red-500 bg-red-950/10' :
                          execStep?.status === 'running' ? 'border-amber-500 bg-amber-950/10' :
                          'border-slate-700 bg-slate-950/30'
                        }`}
                      >
                        <div className={`absolute right-0 top-0 h-full w-1 ${phaseStyle.bar} opacity-50`} />
                        <div className="mb-2 flex items-center gap-2">
                          <span className="text-[10px] text-slate-600">Step {idx + 1}</span>
                          {execStep && <StepBadge status={execStep.status} />}
                          <span className={`inline-flex items-center gap-1 rounded bg-slate-800/70 px-1.5 py-0.5 text-[10px] ${phaseStyle.color}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${phaseStyle.dot}`} />
                            {phaseStyle.label}
                          </span>
                          {execStep?.jailbreak_guidance && (
                            <span className="rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] text-purple-400">AI</span>
                          )}
                        </div>
                        <p className="text-sm font-medium text-slate-200">{attackTitle}</p>
                        {phase !== 'Unknown phase' && (
                          <p className="text-xs text-slate-500">Phase: {phase}</p>
                        )}
                        {attackMitre && (
                          <span className="mt-2 inline-block rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] text-purple-400">{attackMitre}</span>
                        )}
                        {execStep?.jailbreak_guidance && (
                          <div className="mt-3 rounded-lg border border-purple-500/10 bg-purple-950/20 p-2.5">
                            <p className="text-[10px] uppercase tracking-wide text-purple-400">AI Guidance</p>
                            <p className="mt-1 text-xs text-slate-300">{execStep.jailbreak_guidance}</p>
                          </div>
                        )}
                        {execStep?.output && (
                          <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/50 p-2.5 font-mono">
                            <p className="text-[10px] text-slate-600">Output</p>
                            <p className="mt-1 text-xs text-slate-400">{execStep.output}</p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </Panel>
            )}

            {selected &&
              (selected.live_council?.enabled ||
                selected.chain_execution ||
                councilWsEvents.length > 0) && (
              <Panel title="Live Attack Council">
                <CouncilTimeline
                  liveCouncil={selected.live_council}
                  wsEvents={councilWsEvents}
                  chainsVersion={selected.attack_chains?.version}
                />
              </Panel>
            )}

            {selected && (
              <TerminalOutput
                engagementId={selected.id}
                isActive={terminalActive || selected.chain_execution?.status === 'running'}
                councilEvents={councilWsEvents}
                reasoningTrace={selected.reasoning_trace}
              />
            )}
            <RealTimeAttackMonitor engagementId={selected?.id} />
          </div>
        </div>
        )}
      </main>
    </div>
  );
}

export default function AttackDashboard() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center text-slate-400">
          Loading attack dashboard…
        </div>
      }
    >
      <AttackDashboardContent />
    </Suspense>
  );
}
