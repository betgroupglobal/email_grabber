"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Bot,
  ExternalLink,
  Loader2,
  Play,
  Square,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import TerminalOutput from "@/components/attack-monitoring/TerminalOutput";
import CouncilTimeline from "@/components/attack-monitoring/CouncilTimeline";
import { orchestratorWs } from "@/lib/config";
import {
  appendCouncilEvent,
  isCouncilWsMessage,
  type CouncilWsEvent,
  type LiveCouncilState,
} from "@/lib/liveCouncil";
import {
  DEFAULT_GUIDED_TARGET,
  GUIDED_STEPS,
} from "@/lib/guidedAssessment";
import { normalizeTargetInput } from "@/lib/targetUtils";
import {
  approveLiveCouncilDirective,
  fetchGuidedAutonomousStatus,
  forceLiveCouncilReplan,
  startGuidedAutonomous,
  stopGuidedAutonomous,
  type GuidedAutonomousStatus,
} from "@/lib/orchestratorClient";

const PHASE_COUNT = 8;
const OPS_SESSION_KEY = "ops:autonomous-session";

function loadOpsSession(): {
  target: string;
  aggression: number;
  roeAck: boolean;
  webOnly: boolean;
} | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(OPS_SESSION_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as {
      target?: string;
      aggression?: number;
      roeAck?: boolean;
      webOnly?: boolean;
    };
    return {
      target: data.target || DEFAULT_GUIDED_TARGET,
      aggression: data.aggression ?? 5,
      roeAck: Boolean(data.roeAck),
      webOnly: data.webOnly !== false,
    };
  } catch {
    return null;
  }
}

function saveOpsSession(payload: {
  target: string;
  aggression: number;
  roeAck: boolean;
  webOnly: boolean;
}) {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(OPS_SESSION_KEY, JSON.stringify(payload));
  } catch {
    /* ignore quota */
  }
}

export interface UnifiedRunState {
  engagementId: string | null;
  target: string;
  aggression: number;
  status: GuidedAutonomousStatus | null;
  liveCouncil?: LiveCouncilState;
  councilEvents: CouncilWsEvent[];
  chainsVersion?: number;
  running: boolean;
  starting: boolean;
  approving: boolean;
  replanning: boolean;
  handleApprove: () => Promise<void>;
  handleForceReplan: () => Promise<void>;
  handleStop: () => Promise<void>;
  handleRerun: () => Promise<void>;
  handleNewTarget: () => void;
  orchestratorWsConnected?: boolean;
}

export interface GuidedAutonomousPanelProps {
  /** Hide standalone page-style intro when embedded in unified ops */
  embedded?: boolean;
  /** Single-run unified ops: slim controls, terminal owned by parent */
  unifiedRun?: boolean;
  showTerminal?: boolean;
  showCouncilTimeline?: boolean;
  /** Pre-select an existing engagement (e.g. from ?engagement= URL) */
  initialEngagementId?: string | null;
  onEngagementChange?: (ctx: {
    engagementId: string | null;
    target: string;
    aggression: number;
    status: GuidedAutonomousStatus | null;
  }) => void;
  onRunStateChange?: (state: UnifiedRunState) => void;
}

export function GuidedAutonomousPanel({
  embedded = false,
  unifiedRun = false,
  showTerminal = true,
  showCouncilTimeline = true,
  initialEngagementId = null,
  onEngagementChange,
  onRunStateChange,
}: GuidedAutonomousPanelProps) {
  const savedSession = loadOpsSession();
  const [targetRaw, setTargetRaw] = useState(savedSession?.target ?? DEFAULT_GUIDED_TARGET);
  const [aggression, setAggression] = useState(savedSession?.aggression ?? 5);
  const [roeAck, setRoeAck] = useState(savedSession?.roeAck ?? true);
  const [webOnly, setWebOnly] = useState(savedSession?.webOnly ?? true);
  const [engagementId, setEngagementId] = useState<string | null>(null);
  const [status, setStatus] = useState<GuidedAutonomousStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jailbreakConfigured, setJailbreakConfigured] = useState<boolean | null>(null);
  const [liveCouncil, setLiveCouncil] = useState<LiveCouncilState | undefined>();
  const [councilEvents, setCouncilEvents] = useState<CouncilWsEvent[]>([]);
  const [approving, setApproving] = useState(false);
  const [replanning, setReplanning] = useState(false);
  const [chainsVersion, setChainsVersion] = useState<number | undefined>();
  const [orchestratorWsConnected, setOrchestratorWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const prevEngagementRef = useRef<string | null>(null);

  const normalizedTarget = normalizeTargetInput(targetRaw);
  const running =
    status?.guided_autonomous?.status === "running" ||
    status?.guided_autonomous?.status === "starting" ||
    status?.guided_autonomous?.status === "stopping";
  const currentPhase = status?.guided_autonomous?.current_phase ?? 0;

  const refreshStatus = useCallback(async (id: string) => {
    const s = await fetchGuidedAutonomousStatus(id);
    if (!s) return;
    setStatus(s);
    if (s.live_council) setLiveCouncil(s.live_council);
    if (s.attack_chains?.version != null) setChainsVersion(s.attack_chains.version);
  }, []);

  useEffect(() => {
    if (!initialEngagementId || engagementId) return;
    setEngagementId(initialEngagementId);
    void refreshStatus(initialEngagementId);
  }, [initialEngagementId, engagementId, refreshStatus]);

  useEffect(() => {
    saveOpsSession({
      target: targetRaw,
      aggression,
      roeAck,
      webOnly,
    });
  }, [targetRaw, aggression, roeAck, webOnly]);

  useEffect(() => {
    const prev = prevEngagementRef.current;
    if (prev && prev !== engagementId) {
      setCouncilEvents([]);
      setLiveCouncil(undefined);
      setChainsVersion(undefined);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setOrchestratorWsConnected(false);
    }
    prevEngagementRef.current = engagementId;
  }, [engagementId]);

  useEffect(() => {
    if (!engagementId) return;
    const id = engagementId;

    const poll = setInterval(() => {
      void refreshStatus(id);
    }, 3000);

    let intentionalClose = false;
    const ws = new WebSocket(`${orchestratorWs("/")}?engagement=${id}`);
    wsRef.current = ws;
    ws.onopen = () => setOrchestratorWsConnected(true);
    ws.onclose = () => setOrchestratorWsConnected(false);
    ws.onerror = () => setOrchestratorWsConnected(false);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string) as {
          guided_autonomous?: GuidedAutonomousStatus["guided_autonomous"];
          status?: string;
          live_council?: LiveCouncilState;
          attack_chains?: { version?: number };
          scan_session?: GuidedAutonomousStatus["scan_session"];
        };
        if (isCouncilWsMessage(data)) {
          setCouncilEvents((prev) => appendCouncilEvent(prev, data));
        }
        if (data.live_council) setLiveCouncil(data.live_council);
        if (data.attack_chains?.version != null) setChainsVersion(data.attack_chains.version);
        if (data.guided_autonomous || data.scan_session !== undefined) {
          setStatus((prev) =>
            prev
              ? {
                  ...prev,
                  status: data.status || prev.status,
                  guided_autonomous: data.guided_autonomous || prev.guided_autonomous,
                  scan_session:
                    data.scan_session !== undefined ? data.scan_session : prev.scan_session,
                }
              : null
          );
        }
      } catch {
        /* ignore */
      }
    };

    return () => {
      clearInterval(poll);
      intentionalClose = true;
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      ws.close();
      setOrchestratorWsConnected(false);
    };
  }, [engagementId, refreshStatus]);

  const resetRunState = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setEngagementId(null);
    setStatus(null);
    setCouncilEvents([]);
    setLiveCouncil(undefined);
    setChainsVersion(undefined);
    setError(null);
    setOrchestratorWsConnected(false);
  }, []);

  const handleRerun = useCallback(async () => {
    if (!normalizedTarget) {
      setError("Enter a valid target.");
      return;
    }
    resetRunState();
    setStarting(true);
    try {
      const result = await startGuidedAutonomous({
        target: normalizedTarget,
        aggression_level: aggression,
        roe_acknowledged: roeAck,
        web_only: webOnly,
      });
      if (!result.ok) {
        setError(String(result.body.error || `Start failed (${result.status})`));
        return;
      }
      setEngagementId(result.data.engagement_id);
      setJailbreakConfigured(result.data.jailbreak_api_configured ?? null);
      await refreshStatus(result.data.engagement_id);
    } finally {
      setStarting(false);
    }
  }, [
    roeAck,
    normalizedTarget,
    aggression,
    webOnly,
    resetRunState,
    refreshStatus,
  ]);

  const handleNewTarget = useCallback(() => {
    resetRunState();
  }, [resetRunState]);

  const handleStart = async () => {
    if (!normalizedTarget) {
      setError("Enter a valid target.");
      return;
    }
    setError(null);
    setStarting(true);
    try {
      const result = await startGuidedAutonomous({
        target: normalizedTarget,
        aggression_level: aggression,
        roe_acknowledged: roeAck,
        web_only: webOnly,
      });
      if (!result.ok) {
        setError(String(result.body.error || `Start failed (${result.status})`));
        return;
      }
      setEngagementId(result.data.engagement_id);
      setJailbreakConfigured(result.data.jailbreak_api_configured ?? null);
      await refreshStatus(result.data.engagement_id);
    } finally {
      setStarting(false);
    }
  };

  const handleStop = useCallback(async () => {
    if (!engagementId) return;
    await stopGuidedAutonomous(engagementId);
    await refreshStatus(engagementId);
  }, [engagementId, refreshStatus]);

  const handleApproveCouncil = useCallback(async () => {
    if (!engagementId) return;
    setApproving(true);
    try {
      await approveLiveCouncilDirective(engagementId);
      await refreshStatus(engagementId);
    } finally {
      setApproving(false);
    }
  }, [engagementId, refreshStatus]);

  const handleForceReplan = useCallback(async () => {
    if (!engagementId) return;
    setReplanning(true);
    try {
      await forceLiveCouncilReplan(engagementId);
      await refreshStatus(engagementId);
    } finally {
      setReplanning(false);
    }
  }, [engagementId, refreshStatus]);

  const phases = status?.guided_autonomous?.phases || [];
  const lastSource =
    status?.guided_autonomous?.last_ai_source ||
    status?.guided_autonomous?.jailbreak_sources?.slice(-1)[0];
  const lastAiLatency = status?.guided_autonomous?.last_ai_latency_ms;

  useEffect(() => {
    onEngagementChange?.({
      engagementId,
      target: normalizedTarget,
      aggression,
      status,
    });
  }, [engagementId, normalizedTarget, aggression, status, onEngagementChange]);

  useEffect(() => {
    onRunStateChange?.({
      engagementId,
      target: normalizedTarget,
      aggression,
      status,
      liveCouncil,
      councilEvents,
      chainsVersion,
      running,
      starting,
      approving,
      replanning,
    handleApprove: handleApproveCouncil,
    handleForceReplan,
    handleStop,
    handleRerun,
    handleNewTarget,
    orchestratorWsConnected,
  });
}, [
  engagementId,
  normalizedTarget,
  aggression,
  status,
  liveCouncil,
  councilEvents,
  chainsVersion,
  running,
  starting,
  approving,
  replanning,
  handleApproveCouncil,
  handleForceReplan,
  handleStop,
  handleRerun,
  handleNewTarget,
  orchestratorWsConnected,
  onRunStateChange,
]);

  const compactControls = embedded || unifiedRun;

  return (
    <div className={compactControls ? "space-y-3" : "space-y-6"}>
      <div
        className={
          compactControls
            ? "rounded-lg border border-slate-800 bg-slate-900/50 p-3"
            : "rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-5"
        }
      >
        {!embedded && !unifiedRun && (
          <div className="mb-4 flex items-start gap-3">
            <Bot className="mt-0.5 h-6 w-6 shrink-0 text-cyan-400" />
            <div>
              <h2 className="text-lg font-semibold text-cyan-300">Autonomous mode</h2>
              <p className="text-sm text-slate-400">
                Jailbreak AI drives all 8 phases with Live Attack Council pivot/reasoning on
                failures — Hub tools, OpSec assess, and execute-chain with live terminal output.
              </p>
            </div>
          </div>
        )}

        {jailbreakConfigured === false && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-sm text-amber-200">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            JAILBREAK_API_KEY not set — pipeline uses heuristic fallback (logs show{" "}
            <code className="text-amber-100">heuristic_no_api_key</code>).
          </div>
        )}

        <div className={compactControls ? "grid gap-3 md:grid-cols-[1fr_auto_auto]" : "grid gap-4 md:grid-cols-2"}>
          <label className="block text-sm">
            <span className={compactControls ? "text-[10px] text-slate-500" : "text-slate-400"}>
              Target URL
            </span>
            <input
              className={
                compactControls
                  ? "mt-0.5 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 font-mono text-xs text-white"
                  : "mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
              }
              value={targetRaw}
              onChange={(e) => setTargetRaw(e.target.value)}
              disabled={running}
              placeholder={DEFAULT_GUIDED_TARGET}
            />
          </label>
          <label className="block text-sm">
            <span className={compactControls ? "text-[10px] text-slate-500" : "text-slate-400"}>
              Aggression (1–10)
            </span>
            <input
              type="range"
              min={1}
              max={10}
              value={aggression}
              onChange={(e) => setAggression(Number(e.target.value))}
              disabled={running}
              className={compactControls ? "mt-1 w-full" : "mt-2 w-full"}
            />
            <span className={compactControls ? "text-[10px] text-cyan-400" : "text-cyan-400"}>
              {aggression}
            </span>
          </label>
          {!compactControls && (
            <div className="hidden md:block" aria-hidden />
          )}
        </div>

        <div className={`${compactControls ? "mt-2" : "mt-3"} flex flex-wrap gap-3 text-sm`}>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={roeAck}
              onChange={(e) => setRoeAck(e.target.checked)}
              disabled={running}
            />
            <span className={compactControls ? "text-[11px] text-slate-300" : "text-slate-300"}>
              Authorized engagement (ROE on file)
            </span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={webOnly}
              onChange={(e) => setWebOnly(e.target.checked)}
              disabled={running}
            />
            <span className={compactControls ? "text-[11px] text-slate-300" : "text-slate-300"}>
              Scope: HTTP(S) web assets only
            </span>
          </label>
        </div>

        {error && (
          <p className={`${compactControls ? "mt-2 text-xs" : "mt-3 text-sm"} text-red-400`}>
            {error}
          </p>
        )}

        <div className={`${compactControls ? "mt-2" : "mt-4"} flex flex-wrap gap-2`}>
          <Button
            onClick={() => void handleStart()}
            disabled={starting || running || !normalizedTarget}
            size={compactControls ? "sm" : "default"}
            className="bg-cyan-600 hover:bg-cyan-500"
          >
            {starting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            {compactControls ? "Start run" : "Start autonomous assessment"}
          </Button>
          {engagementId && running && (
            <Button variant="outline" size={compactControls ? "sm" : "default"} onClick={() => void handleStop()}>
              <Square className="mr-2 h-4 w-4" />
              Stop
            </Button>
          )}
          {engagementId && !unifiedRun && (
            <Link
              href={`/engagement/${engagementId}`}
              className="inline-flex items-center gap-1 text-sm text-cyan-400 hover:underline"
            >
              Open engagement <ExternalLink className="h-3 w-3" />
            </Link>
          )}
        </div>
      </div>

      {engagementId && (
        <>
          <div
            className={
              unifiedRun
                ? "rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2"
                : "rounded-xl border border-slate-800 bg-slate-900/40 p-4"
            }
          >
            {!unifiedRun && (
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm text-slate-400">
                  Engagement <code className="text-cyan-400">{engagementId}</code>
                  {lastSource && (
                    <>
                      {" "}
                      · AI source: <code className="text-emerald-400">{lastSource}</code>
                      {lastAiLatency != null && (
                        <span className="text-slate-500"> · {lastAiLatency}ms</span>
                      )}
                    </>
                  )}
                </span>
                <span className="text-sm font-medium text-white">
                  {status?.guided_autonomous?.status || status?.status || "—"}
                  {currentPhase > 0 && ` · Phase ${currentPhase}/${PHASE_COUNT}`}
                </span>
              </div>
            )}
            {unifiedRun ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
                  Phases
                </span>
                <span className="text-[10px] text-slate-600">·</span>
                <span className="font-mono text-[10px] text-cyan-300">
                  {status?.guided_autonomous?.status || status?.status || "—"}
                  {currentPhase > 0 && ` · ${currentPhase}/${PHASE_COUNT}`}
                </span>
                {lastSource && (
                  <>
                    <span className="text-[10px] text-slate-600">·</span>
                    <span className="font-mono text-[10px] text-emerald-400">
                      {lastSource}
                      {lastAiLatency != null ? ` ${lastAiLatency}ms` : ""}
                    </span>
                  </>
                )}
                <div className="flex min-w-0 flex-1 flex-wrap gap-1">
                  {GUIDED_STEPS.map((meta) => {
                    const rec = phases.find((p) => p.phase_number === meta.step);
                    const active = currentPhase === meta.step;
                    const done = rec?.status === "complete" || rec?.status === "skipped";
                    return (
                      <span
                        key={meta.step}
                        title={`${meta.step}. ${meta.title}${rec ? ` — ${rec.status}` : ""}`}
                        className={`rounded px-1.5 py-0.5 font-mono text-[9px] ${
                          active
                            ? "bg-cyan-950/60 text-cyan-300 ring-1 ring-cyan-500/40"
                            : done
                              ? "bg-emerald-950/40 text-emerald-400/90"
                              : "bg-slate-950/60 text-slate-500"
                        }`}
                      >
                        {meta.step}
                      </span>
                    );
                  })}
                </div>
              </div>
            ) : (
              <>
                <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {GUIDED_STEPS.map((meta) => {
                    const rec = phases.find((p) => p.phase_number === meta.step);
                    const active = currentPhase === meta.step;
                    const done = rec?.status === "complete" || rec?.status === "skipped";
                    return (
                      <li
                        key={meta.step}
                        className={`rounded-lg border px-3 py-2 text-xs ${
                          active
                            ? "border-cyan-500 bg-cyan-950/40"
                            : done
                              ? "border-emerald-800/60 bg-emerald-950/20"
                              : "border-slate-800 bg-slate-950/50"
                        }`}
                      >
                        <span className="font-medium text-slate-200">
                          {meta.step}. {meta.title}
                        </span>
                        {rec && (
                          <p className="mt-1 text-slate-500">
                            {rec.status}
                            {rec.ai_source ? ` · ${rec.ai_source}` : ""}
                            {"ai_latency_ms" in rec && rec.ai_latency_ms != null
                              ? ` · ${rec.ai_latency_ms}ms`
                              : ""}
                            {"council_turn_id" in rec && rec.council_turn_id && (
                              <> · council {String(rec.council_turn_id).slice(0, 8)}</>
                            )}
                            {"council_turn" in rec &&
                              !rec.council_turn_id &&
                              rec.council_turn != null && (
                                <> · council turn {rec.council_turn}</>
                              )}
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ol>
                {phases.length > 0 && (
                  <details className="mt-4 text-sm text-slate-400">
                    <summary className="cursor-pointer text-cyan-400">Phase narratives</summary>
                    <ul className="mt-2 space-y-3">
                      {phases.map((p) => {
                        const executed = (p as { tools_executed?: Array<{ plugin?: string; tool?: string; success?: boolean }> }).tools_executed
                          || (p as { tool_results?: Array<{ plugin?: string; tool?: string; success?: boolean }> }).tool_results
                          || [];
                        const findings = (p as { findings_summary?: string }).findings_summary;
                        return (
                          <li key={p.phase_number} className="rounded border border-slate-800 p-2">
                            <strong className="text-slate-200">
                              Phase {p.phase_number}: {p.title}
                            </strong>
                            <p className="mt-1 whitespace-pre-wrap text-slate-400">
                              {p.narrative || p.artifact_text || "—"}
                            </p>
                            {executed.length > 0 && (
                              <details className="mt-2 text-xs">
                                <summary className="cursor-pointer text-cyan-400">
                                  Tools run ({executed.length})
                                </summary>
                                <ul className="mt-1 space-y-1 text-slate-500">
                                  {executed.map((tr, i) => (
                                    <li key={i}>
                                      {tr.plugin}
                                      {tr.tool ? `/${tr.tool}` : ""}
                                      {" — "}
                                      <span className={tr.success === false ? "text-amber-400" : "text-emerald-400"}>
                                        {tr.success === false ? "fail" : "ok"}
                                      </span>
                                    </li>
                                  ))}
                                </ul>
                                {findings && (
                                  <p className="mt-2 text-slate-500 whitespace-pre-wrap border-t border-slate-800 pt-2">
                                    {findings}
                                  </p>
                                )}
                              </details>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </details>
                )}
              </>
            )}
          </div>

          {showCouncilTimeline && (
            <div className="rounded-xl border border-purple-500/20 bg-slate-900/40 p-4">
              <CouncilTimeline
                liveCouncil={liveCouncil}
                wsEvents={councilEvents}
                chainsVersion={chainsVersion}
                engagementId={engagementId}
                onApprove={liveCouncil?.pending_directive ? handleApproveCouncil : undefined}
                approving={approving}
              />
            </div>
          )}

          {showTerminal && (
            <div className="rounded-xl border border-slate-800 overflow-hidden">
              <div className="border-b border-slate-800 bg-slate-900/80 px-4 py-2 text-sm text-slate-400">
                Live terminal (Jailbreak AI + Hub)
              </div>
              <div className="h-[320px]">
                <TerminalOutput
                  engagementId={engagementId}
                  isActive={Boolean(engagementId)}
                  fillHeight
                  councilEvents={councilEvents}
                  reasoningTrace={status?.reasoning_trace}
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}