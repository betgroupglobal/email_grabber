"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ChevronDown, ExternalLink, Layers } from "lucide-react";
import {
  GuidedAutonomousPanel,
  type UnifiedRunState,
} from "@/components/guided-assessment/GuidedAutonomousPanel";
import { GuidedAssessmentWizard } from "@/components/guided-assessment/GuidedAssessmentWizard";
import { RunSummaryBanner } from "@/components/operations/RunSummaryBanner";
import {
  UnifiedRunTerminal,
  type SystemFeedLine,
} from "@/components/operations/UnifiedRunTerminal";
import { analyzeMitreTechniques, suggestMitreTechniques } from "@/lib/api";
import { fetchEngagement } from "@/lib/orchestratorClient";
import type { GuidedAutonomousStatus } from "@/lib/orchestratorClient";
import { deriveSuggestedHotkey } from "@/lib/templater/hotkeys";
import {
  resolveCurrentPatternStep,
  type ThoughtPatternStep,
} from "@/lib/thoughtProcessPattern";
import { runStageTransition } from "@/lib/templater/stageTransitionTemplates";

export interface EngagementContext {
  engagementId: string | null;
  target: string;
  aggression: number;
  status: GuidedAutonomousStatus | null;
}

const MITRE_DEBOUNCE_MS = 2200;

function mitreSourceLabel(source?: string): string {
  if (!source) return "";
  if (source === "jailbreak_ai" || source === "jailbreak_api") return " · via jailbreak_ai";
  if (source === "openrouter") return " · via openrouter";
  if (source === "heuristic" || source.startsWith("heuristic")) return " · via heuristic";
  return ` · via ${source}`;
}

export function UnifiedOperationsHub() {
  const searchParams = useSearchParams();
  const [ctx, setCtx] = useState<EngagementContext>({
    engagementId: null,
    target: "",
    aggression: 5,
    status: null,
  });
  const [runState, setRunState] = useState<UnifiedRunState | null>(null);
  const [systemLines, setSystemLines] = useState<SystemFeedLine[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(
    searchParams.get("panel") === "manual"
  );
  const [thoughtRailCollapsed, setThoughtRailCollapsed] = useState(false);
  const feedKeys = useRef(new Set<string>());
  const lastPhaseRef = useRef(0);
  const lastPatternStageRef = useRef<ThoughtPatternStep>("orient");
  const mitrePhaseRef = useRef(0);
  const mitreTimerRef = useRef<number | null>(null);

  const pushSystemLine = useCallback((line: SystemFeedLine) => {
    if (feedKeys.current.has(line.key)) return;
    feedKeys.current.add(line.key);
    setSystemLines((prev) => [...prev, line]);
  }, []);

  const handleTemplaterLine = useCallback(
    (line: SystemFeedLine) => {
      pushSystemLine(line);
    },
    [pushSystemLine]
  );

  const attackDescription = useMemo(() => {
    const phases = ctx.status?.guided_autonomous?.phases || [];
    if (phases.length === 0) return undefined;
    return phases
      .filter((p) => p.narrative || p.artifact_text)
      .map((p) => `Phase ${p.phase_number} (${p.title}): ${p.narrative || p.artifact_text}`)
      .join("\n\n");
  }, [ctx.status]);

  const running =
    ctx.status?.guided_autonomous?.status === "running" ||
    ctx.status?.guided_autonomous?.status === "starting";

  const runComplete =
    ctx.status?.guided_autonomous?.status === "complete" ||
    ctx.status?.guided_autonomous?.status === "stopped" ||
    ctx.status?.guided_autonomous?.status === "error";

  const stats = useMemo(() => {
    const ga = ctx.status?.guided_autonomous;
    const summary = ga?.run_summary;
    const councilApprovals =
      summary?.council_approvals ??
      (ctx.status?.live_council?.directives || []).filter(
        (d) => d.approved_at || d.status === "approved"
      ).length;
    return {
      toolsInvoked: summary?.tools_invoked_count ?? ga?.tools_invoked_count ?? 0,
      pathwayAttempts: summary?.pathway_attempts_count ?? ga?.pathway_attempts_count ?? 0,
      councilApprovals,
    };
  }, [ctx.status]);

  // Phase transitions → terminal + templater stage scripts
  useEffect(() => {
    const phase = ctx.status?.guided_autonomous?.current_phase ?? 0;
    const title = ctx.status?.guided_autonomous?.current_phase_title;
    if (!ctx.engagementId || phase <= 0 || phase === lastPhaseRef.current) return;
    lastPhaseRef.current = phase;
    pushSystemLine({
      key: `phase-${ctx.engagementId}-${phase}-${title || ""}`,
      type: "info",
      content: `[hub] Phase ${phase}/8${title ? `: ${title}` : ""}`,
    });

    const trace = runState?.status?.reasoning_trace;
    const current = resolveCurrentPatternStep({
      reasoningTrace: trace,
      liveCouncil: runState?.liveCouncil,
      currentPhase: phase,
      targetSet: Boolean(ctx.target?.trim()),
    });
    const prev = lastPatternStageRef.current;
    if (current !== prev) {
      const tr = runStageTransition(prev, current, { trigger: `phase_${phase}` });
      for (const content of [...tr.thinkLines, ...tr.systemLines]) {
        pushSystemLine({
          key: `templater-phase-${ctx.engagementId}-${phase}-${content.slice(0, 40)}`,
          type: "info",
          content,
        });
      }
      lastPatternStageRef.current = current;
    }
  }, [
    ctx.engagementId,
    ctx.target,
    ctx.status?.guided_autonomous?.current_phase,
    ctx.status?.guided_autonomous?.current_phase_title,
    runState?.status?.reasoning_trace,
    runState?.liveCouncil,
    pushSystemLine,
  ]);

  // Scan session from status API → terminal
  useEffect(() => {
    const scan = ctx.status?.scan_session;
    if (!ctx.engagementId || !scan?.id) return;
    const svc =
      scan.service_count ??
      scan.fingerprint?.services?.length ??
      scan.open_port_count ??
      0;
    pushSystemLine({
      key: `scan-status-${ctx.engagementId}-${scan.id}-${scan.status}-${svc}`,
      type: scan.status === "ready" ? "success" : "scan",
      content: `[scan] Session ${scan.id.slice(0, 8)}… · ${scan.status || "?"}${scan.scan_type ? ` · ${scan.scan_type}` : ""}${svc ? ` · ${svc} services` : ""}`,
    });
    if (scan.status === "ready" && scan.fingerprint?.os) {
      pushSystemLine({
        key: `scan-os-${ctx.engagementId}-${scan.id}-${scan.fingerprint.os}`,
        type: "scan",
        content: `[scan] Fingerprint · OS ${scan.fingerprint.os}`,
      });
    }
  }, [ctx.engagementId, ctx.status?.scan_session, pushSystemLine]);

  // MITRE context → terminal (debounced on phase / narrative changes)
  useEffect(() => {
    const target = ctx.target.trim();
    if (!target) return;

    const phase = ctx.status?.guided_autonomous?.current_phase ?? 0;
    if (phase > 0 && phase === mitrePhaseRef.current && !attackDescription?.trim()) {
      return;
    }
    if (phase > 0) mitrePhaseRef.current = phase;

    if (mitreTimerRef.current) window.clearTimeout(mitreTimerRef.current);

    let cancelled = false;
    mitreTimerRef.current = window.setTimeout(() => {
      void (async () => {
        try {
          if (attackDescription?.trim() && ctx.engagementId) {
            const result = await analyzeMitreTechniques({
              attack_description: attackDescription,
              context: `Engagement ${ctx.engagementId}`,
            });
            if (cancelled) return;
            const top = result.techniques.slice(0, 4);
            pushSystemLine({
              key: `mitre-analyze-${ctx.engagementId}-${phase}-${top.length}`,
              type: "mitre",
              content: `[mitre] mapped${mitreSourceLabel(result.source)} · ${result.chains[0]?.name || "mapping"} — ${result.summary?.slice(0, 180) || "updated"}`,
            });
            top.forEach((t) => {
              pushSystemLine({
                key: `mitre-tech-${t.technique_id}-${ctx.engagementId}-${phase}`,
                type: "mitre",
                content: `[mitre] ${t.technique_id} ${t.name} (${t.tactic}) · ${Math.round(t.confidence * 100)}%`,
              });
            });
          } else if (!running || phase <= 2) {
            const result = await suggestMitreTechniques({
              target,
              aggression_level: ctx.aggression,
            });
            if (cancelled) return;
            pushSystemLine({
              key: `mitre-suggest-${target}-${ctx.aggression}-${phase}`,
              type: "mitre",
              content: `[mitre] mapped${mitreSourceLabel(result.source)} · ${result.recommended_chain?.name || "suggest"} — ${result.analysis?.slice(0, 180) || "ready"}`,
            });
            (result.primary_techniques || []).slice(0, 4).forEach((t) => {
              pushSystemLine({
                key: `mitre-suggest-${t.technique_id}-${target}-${phase}`,
                type: "mitre",
                content: `[mitre] ${t.technique_id} ${t.name} · priority ${t.priority}/10`,
              });
            });
          }
        } catch (err) {
          if (cancelled) return;
          const hint = deriveSuggestedHotkey(runState?.liveCouncil);
          pushSystemLine({
            key: `mitre-err-${ctx.engagementId}-${phase}-${Date.now()}`,
            type: "warning",
            content: `[mitre] ${err instanceof Error ? err.message : "analysis unavailable"}${
              hint ? ` — suggested: ${hint.hotkeyLabel}` : ""
            }`,
          });
        }
      })();
    }, MITRE_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      if (mitreTimerRef.current) {
        window.clearTimeout(mitreTimerRef.current);
        mitreTimerRef.current = null;
      }
    };
  }, [
    ctx.target,
    ctx.aggression,
    ctx.engagementId,
    attackDescription,
    ctx.status?.guided_autonomous?.current_phase,
    running,
    runState?.liveCouncil,
    pushSystemLine,
  ]);

  // Attack chains + execution → terminal
  useEffect(() => {
    const id = ctx.engagementId;
    if (!id) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const data = await fetchEngagement(id);
        if (cancelled) return;
        const chains = data.attack_chains?.chains || [];
        const version = data.attack_chains?.version ?? 0;
        const execId = data.chain_execution?.execution_id;
        const opsecRisk = data.opsec_reports?.risk_score;

        if (opsecRisk != null) {
          pushSystemLine({
            key: `opsec-risk-${id}-${opsecRisk}`,
            type: "opsec",
            content: `[opsec] Risk score ${opsecRisk}/100`,
          });
        }

        if (chains.length > 0) {
          pushSystemLine({
            key: `chains-count-${id}-v${version}-${chains.length}`,
            type: "chain",
            content: `[chain] ${chains.length} chain(s) available · v${version}`,
          });
          chains.slice(0, 3).forEach(
            (
              chain: { steps?: unknown[]; steps_count?: number; confidence?: number },
              idx: number
            ) => {
              const steps = chain.steps?.length ?? chain.steps_count ?? 0;
              pushSystemLine({
                key: `chain-${id}-v${version}-${idx}-${steps}`,
                type: "chain",
                content: `[chain] Chain ${idx + 1}: ${steps} steps${chain.confidence != null ? ` · ${Math.round(chain.confidence * 100)}% conf` : ""}`,
              });
            }
          );
        }

        if (execId) {
          pushSystemLine({
            key: `chain-exec-${id}-${execId}`,
            type: "chain",
            content: `[chain] Execution active · ${execId.slice(0, 12)}…`,
          });
        }

        if (data.scan_session?.id && !ctx.status?.scan_session) {
          const s = data.scan_session;
          pushSystemLine({
            key: `scan-eng-${id}-${s.id}-${s.status}`,
            type: "scan",
            content: `[scan] ${s.status || "?"} · session ${String(s.id).slice(0, 8)}…`,
          });
        }
      } catch {
        /* ignore transient fetch errors */
      }
    };

    void poll();
    const interval = window.setInterval(() => void poll(), 8000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [ctx.engagementId, ctx.status?.scan_session, runState?.chainsVersion, pushSystemLine]);

  // Council chain versioning
  useEffect(() => {
    if (!runState?.chainsVersion || !ctx.engagementId) return;
    pushSystemLine({
      key: `chain-version-${ctx.engagementId}-${runState.chainsVersion}`,
      type: "council",
      content: `[council] Chain replanned · version ${runState.chainsVersion}`,
    });
  }, [runState?.chainsVersion, ctx.engagementId, pushSystemLine]);

  // Council WS events → prefixed feed lines
  useEffect(() => {
    if (!runState?.councilEvents?.length || !ctx.engagementId) return;
    const latest = runState.councilEvents[runState.councilEvents.length - 1];
    const key = `council-ws-${ctx.engagementId}-${JSON.stringify(latest).slice(0, 80)}`;
    if (latest.type === "chain_versioned") {
      pushSystemLine({
        key,
        type: "chain",
        content: `[chain] Version ${latest.version}${latest.diff_summary ? ` · ${latest.diff_summary.slice(0, 120)}` : ""}`,
      });
    } else if (latest.type === "execution_paused") {
      const hint = deriveSuggestedHotkey(runState.liveCouncil);
      pushSystemLine({
        key,
        type: "council",
        content: `[council] Execution paused · ${latest.reason}${
          hint ? ` — press ${hint.hotkeyLabel} to ${hint.message}` : ""
        }`,
      });
    }
  }, [runState?.councilEvents, runState?.liveCouncil, ctx.engagementId, pushSystemLine]);

  // Hub/tool errors from reasoning trace
  useEffect(() => {
    const trace = runState?.status?.reasoning_trace;
    if (!trace?.length || !ctx.engagementId) return;
    const last = trace[trace.length - 1] as {
      action?: string;
      note?: string;
      plugin?: string;
      external_tool?: boolean;
    };
    if (last.action !== "tool_failed" && !String(last.note || "").includes("failed")) return;
    const hint = deriveSuggestedHotkey(runState?.liveCouncil);
    pushSystemLine({
      key: `tool-fail-hint-${ctx.engagementId}-${last.plugin}-${String(last.note).slice(0, 40)}`,
      type: "warning",
      content: `[tool] ${last.plugin || "hub"} failed — ${last.note || "see log"}${
        hint ? ` · Try ${hint.hotkeyLabel} (${hint.message})` : " · Shift+R replan"
      }`,
    });
  }, [runState?.status?.reasoning_trace, runState?.liveCouncil, ctx.engagementId, pushSystemLine]);

  useEffect(() => {
    if (!ctx.engagementId) {
      feedKeys.current.clear();
      setSystemLines([]);
      lastPhaseRef.current = 0;
      lastPatternStageRef.current = "orient";
      mitrePhaseRef.current = 0;
    }
  }, [ctx.engagementId]);

  const pendingDirective = runState?.liveCouncil?.pending_directive;
  const isScanPivot =
    pendingDirective?.action === "pivot_chain" ||
    pendingDirective?.failure_class?.includes("scan");

  return (
    <div className="flex h-[calc(100vh-3rem)] min-h-0 flex-col bg-[#080c14] text-white -m-6 lg:-m-8">
      <header className="z-40 shrink-0 border-b border-slate-800/60 bg-[#080c14]/90 backdrop-blur-xl">
        <div className="mx-auto max-w-[1600px] px-4 py-2.5 lg:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-purple-600 shadow-lg shadow-cyan-500/20">
                <Layers className="h-4 w-4 text-white" />
              </div>
              <div>
                <h1 className="text-base font-bold text-white">Autonomous Operations</h1>
                <p className="text-[10px] text-slate-500">
                  Target · phases · thought rail · unified terminal
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {running && (
                <span className="flex items-center gap-1.5 rounded-full border border-cyan-500/30 bg-cyan-950/40 px-2.5 py-0.5 text-[10px] text-cyan-300">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />
                  Run active · continues in background if you leave
                </span>
              )}
              {ctx.status?.policy?.allow_high_risk && (
                <span className="rounded-full border border-amber-500/40 bg-amber-950/40 px-2.5 py-0.5 text-[10px] text-amber-200">
                  High-risk mode: operations not blocked
                </span>
              )}
              {ctx.status?.scan_session?.status === "scanning" && (
                <span className="flex items-center gap-1 rounded-full border border-teal-500/30 bg-teal-950/40 px-2.5 py-0.5 text-[10px] text-teal-300">
                  Scanning
                </span>
              )}
              {ctx.engagementId && (
                <Link
                  href={`/engagement/${ctx.engagementId}`}
                  className="inline-flex items-center gap-1 text-[10px] text-cyan-400 hover:underline"
                >
                  Engagement <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto flex min-h-0 w-full max-w-[1600px] flex-1 flex-col gap-2 px-4 py-3 lg:px-6">
        <GuidedAutonomousPanel
          embedded
          unifiedRun
          showTerminal={false}
          showCouncilTimeline={false}
          initialEngagementId={searchParams.get("engagement")}
          onEngagementChange={setCtx}
          onRunStateChange={setRunState}
        />

        {runComplete && (
          <RunSummaryBanner
            status={ctx.status}
            onRerun={runState?.handleRerun}
            onNewTarget={runState?.handleNewTarget}
            rerunning={runState?.starting}
          />
        )}

        {runState?.engagementId ? (
          <UnifiedRunTerminal
            engagementId={runState.engagementId}
            isActive
            target={ctx.target}
            currentPhase={ctx.status?.guided_autonomous?.current_phase}
            councilEvents={runState.councilEvents}
            reasoningTrace={runState.status?.reasoning_trace}
            systemLines={systemLines}
            liveCouncil={runState.liveCouncil}
            onApprove={
              runState.liveCouncil?.pending_directive
                ? runState.handleApprove
                : undefined
            }
            onForceReplan={runState.handleForceReplan}
            onTemplaterLine={handleTemplaterLine}
            hotkeysEnabled={running || Boolean(runState.liveCouncil?.pending_directive)}
            approving={runState.approving}
            replanning={runState.replanning}
            directiveHint={
              isScanPivot
                ? "Scan pivot — approve to apply council chain/scanner directive"
                : undefined
            }
            thoughtRailCollapsed={thoughtRailCollapsed}
            onThoughtRailCollapsedChange={setThoughtRailCollapsed}
            orchestratorWsConnected={runState.orchestratorWsConnected}
            toolsInvokedCount={stats.toolsInvoked}
            pathwayAttemptsCount={stats.pathwayAttempts}
            councilApprovals={stats.councilApprovals}
            className="min-h-0 flex-1"
          />
        ) : (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-slate-950/30 px-6 py-12 text-center">
            <p className="font-mono text-xs text-slate-400">
              Enter target URL, confirm ROE, and start run
            </p>
            <p className="mt-1 max-w-md text-[10px] text-slate-600">
              Probe tools, MITRE mapping, chains, and Live Attack Council stream into one terminal.
              Advanced manual wizard is optional below.
            </p>
          </div>
        )}

        <details
          className="shrink-0 rounded-lg border border-slate-800/80 bg-slate-900/20"
          open={showAdvanced}
          onToggle={(e) => setShowAdvanced((e.target as HTMLDetailsElement).open)}
        >
          <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-[11px] text-slate-500 marker:content-none [&::-webkit-details-marker]:hidden">
            <ChevronDown className="h-3.5 w-3.5" />
            Advanced — manual guided wizard
          </summary>
          <div className="border-t border-slate-800 p-3">
            <GuidedAssessmentWizard />
          </div>
        </details>
      </main>
    </div>
  );
}
