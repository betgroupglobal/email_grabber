"use client";

import { useCallback, useMemo, useState } from "react";
import { Loader2, RefreshCw, Shield, ThumbsUp, Wifi, WifiOff } from "lucide-react";
import TerminalOutput, {
  type SystemFeedLine,
} from "@/components/attack-monitoring/TerminalOutput";
import { HotkeyHintBar } from "@/components/operations/HotkeyHintBar";
import { ThoughtProcessPanel } from "@/components/operations/ThoughtProcessPanel";
import {
  directiveActionLabel,
  type CouncilWsEvent,
  type LiveCouncilState,
  type ReasoningTraceEntry,
} from "@/lib/liveCouncil";
import type { LiveDirective } from "@/lib/liveCouncilSchema";
import { deriveSuggestedHotkey, suggestedFromDirectiveFields } from "@/lib/templater/hotkeys";
import { runStageTransitionTemplate } from "@/lib/templater/templaterRunner";
import { useTemplaterHotkeys } from "@/lib/templater/useTemplaterHotkeys";
import {
  resolveCurrentPatternStep,
  type ThoughtPatternStep,
} from "@/lib/thoughtProcessPattern";
import { cn } from "@/lib/utils";

export type { SystemFeedLine };

export interface UnifiedRunTerminalProps {
  engagementId: string;
  isActive: boolean;
  target?: string;
  currentPhase?: number;
  councilEvents?: CouncilWsEvent[];
  reasoningTrace?: ReasoningTraceEntry[];
  systemLines?: SystemFeedLine[];
  liveCouncil?: LiveCouncilState;
  onApprove?: () => void | Promise<void>;
  onForceReplan?: () => void | Promise<void>;
  onTemplaterLine?: (line: SystemFeedLine) => void;
  hotkeysEnabled?: boolean;
  approving?: boolean;
  replanning?: boolean;
  className?: string;
  /** Context hint when council directive relates to scan pivot */
  directiveHint?: string;
  thoughtRailCollapsed?: boolean;
  onThoughtRailCollapsedChange?: (collapsed: boolean) => void;
  terminalWsConnected?: boolean;
  orchestratorWsConnected?: boolean;
  toolsInvokedCount?: number;
  pathwayAttemptsCount?: number;
  councilApprovals?: number;
}

function DirectiveSummary({
  directive,
  hint,
  liveCouncil,
}: {
  directive: LiveDirective;
  hint?: string;
  liveCouncil?: LiveCouncilState;
}) {
  const action = directive.action || "continue";
  const isHold = action === "abort";
  const opsecNote = directive.opsec_veto;
  return (
    <div className="min-w-0 flex-1">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-cyan-300">
          Council directive (informational)
        </span>
        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-300">
          {directiveActionLabel(action)}
        </span>
        {opsecNote && (
          <span className="rounded bg-slate-700/80 px-1.5 py-0.5 text-[10px] text-slate-300">
            OpSec note
          </span>
        )}
        {directive.turn != null && (
          <span className="text-[10px] text-slate-500">turn #{directive.turn}</span>
        )}
      </div>
      {directive.rationale && (
        <p className="mt-0.5 line-clamp-2 text-[10px] leading-snug text-slate-400">
          {directive.rationale}
        </p>
      )}
      {hint && (
        <p className="mt-0.5 text-[10px] text-cyan-400/90">{hint}</p>
      )}
      {(() => {
        const aiHint =
          suggestedFromDirectiveFields(directive) ??
          deriveSuggestedHotkey(liveCouncil ?? { pending_directive: directive });
        if (!aiHint) return null;
        return (
          <p className="mt-0.5 text-[10px] text-violet-300/90">
            AI suggests: press{" "}
            <kbd className="rounded border border-violet-500/40 px-1 text-[9px]">{aiHint.hotkeyLabel}</kbd>{" "}
            — {aiHint.message}
          </p>
        );
      })()}
      {isHold && (
        <p className="mt-0.5 text-[10px] text-amber-400/80">
          Abort requested — confirm before stopping the run.
        </p>
      )}
      {opsecNote && !isHold && (
        <p className="mt-0.5 text-[10px] text-slate-400">
          High-risk OpSec signal logged — execution continues (guardrails disabled).
        </p>
      )}
    </div>
  );
}

export function UnifiedRunTerminal({
  engagementId,
  isActive,
  target,
  currentPhase,
  councilEvents,
  reasoningTrace,
  systemLines,
  liveCouncil,
  onApprove,
  onForceReplan,
  onTemplaterLine,
  hotkeysEnabled = true,
  approving = false,
  replanning = false,
  className,
  directiveHint,
  thoughtRailCollapsed = false,
  onThoughtRailCollapsedChange,
  terminalWsConnected,
  orchestratorWsConnected,
  toolsInvokedCount = 0,
  pathwayAttemptsCount = 0,
  councilApprovals = 0,
}: UnifiedRunTerminalProps) {
  const [directiveNote, setDirectiveNote] = useState("");
  const [railCollapsed, setRailCollapsed] = useState(thoughtRailCollapsed);
  const pending = liveCouncil?.pending_directive;
  const pendingPathway = liveCouncil?.pending_pathway;
  const replans = liveCouncil?.replans_used ?? 0;
  const maxReplans = liveCouncil?.max_replans ?? 5;
  const councilTurn = liveCouncil?.turn ?? 0;

  const currentStage = useMemo(
    () =>
      resolveCurrentPatternStep({
        reasoningTrace,
        liveCouncil,
        currentPhase,
        targetSet: Boolean(target?.trim()),
      }),
    [reasoningTrace, liveCouncil, currentPhase, target]
  );

  const pushTemplaterLine = useCallback(
    (line: SystemFeedLine) => {
      onTemplaterLine?.(line);
    },
    [onTemplaterLine]
  );

  const templaterCtx = useMemo(
    () => ({
      onSystemLine: pushTemplaterLine,
      onApprove,
      onForceReplan,
    }),
    [pushTemplaterLine, onApprove, onForceReplan]
  );

  useTemplaterHotkeys({
    enabled: hotkeysEnabled,
    engagementId,
    isActive,
    currentStage,
    liveCouncil,
    templaterCtx,
  });

  const handleRunStageTemplate = useCallback(
    async (stageId: ThoughtPatternStep) => {
      if (stageId === currentStage) return;
      await runStageTransitionTemplate(currentStage, stageId, {
        engagementId,
        currentStage,
        liveCouncil,
        ...templaterCtx,
      });
    },
    [currentStage, engagementId, liveCouncil, templaterCtx]
  );

  const handleApprove = useCallback(() => {
    void onApprove?.();
    setDirectiveNote("");
  }, [onApprove]);

  const setCollapsed = useCallback(
    (v: boolean) => {
      setRailCollapsed(v);
      onThoughtRailCollapsedChange?.(v);
    },
    [onThoughtRailCollapsedChange]
  );

  const wsLive =
    terminalWsConnected !== undefined
      ? terminalWsConnected
      : orchestratorWsConnected !== false;
  const orchLive = orchestratorWsConnected !== false;

  return (
    <div
      className={cn(
        "flex min-h-0 flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-950/50",
        className
      )}
    >
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-800 bg-slate-900/80 px-3 py-1.5">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-slate-400">
            Run terminal
          </span>
          <span className="text-[10px] text-slate-600">·</span>
          <span className="font-mono text-[10px] text-violet-400/90">
            council {councilTurn}
          </span>
          <span className="text-[10px] text-slate-600">·</span>
          <span className="font-mono text-[10px] text-slate-500">
            replans {replans}/{maxReplans}
          </span>
          <span className="hidden text-[10px] text-slate-600 sm:inline">·</span>
          <span className="hidden font-mono text-[10px] text-slate-500 sm:inline">
            tools {toolsInvokedCount} · pathways {pathwayAttemptsCount} · approvals{" "}
            {councilApprovals}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[9px]",
              wsLive
                ? "bg-emerald-950/50 text-emerald-400 ring-1 ring-emerald-500/25"
                : "bg-red-950/50 text-red-400 ring-1 ring-red-500/25"
            )}
            title="Terminal WebSocket"
          >
            {wsLive ? <Wifi className="size-2.5" /> : <WifiOff className="size-2.5" />}
            WS
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[9px]",
              orchLive
                ? "bg-cyan-950/50 text-cyan-400 ring-1 ring-cyan-500/25"
                : "bg-red-950/50 text-red-400 ring-1 ring-red-500/25"
            )}
            title="Orchestrator engagement stream"
          >
            {orchLive ? <Wifi className="size-2.5" /> : <WifiOff className="size-2.5" />}
            Orch
          </span>
          {liveCouncil?.enabled && (
            <span className="inline-flex items-center gap-1 rounded-full bg-violet-950/50 px-2 py-0.5 text-[10px] text-violet-300 ring-1 ring-violet-500/25">
              <Shield className="size-2.5" />
              Council
            </span>
          )}
          <span className="font-mono text-[10px] text-slate-600">{engagementId.slice(0, 8)}…</span>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <ThoughtProcessPanel
          reasoningTrace={reasoningTrace}
          councilEvents={councilEvents}
          liveCouncil={liveCouncil}
          currentPhase={currentPhase}
          target={target}
          collapsed={railCollapsed}
          onCollapsedChange={setCollapsed}
          onRunStageTemplate={handleRunStageTemplate}
        />
        <div className="min-h-0 min-w-0 flex-1">
          <TerminalOutput
            engagementId={engagementId}
            isActive={isActive}
            fillHeight
            compact
            councilEvents={councilEvents}
            reasoningTrace={reasoningTrace}
            systemLines={systemLines}
          />
        </div>
      </div>

      {(pending || pendingPathway || onForceReplan) && (
        <div className="shrink-0 border-t border-slate-800 bg-[#0d1117] px-3 py-2">
          {(pending || pendingPathway) && (
            <HotkeyHintBar liveCouncil={liveCouncil} className="mb-2" />
          )}
          {pendingPathway && !pending && (
            <div className="mb-2 flex gap-2 rounded-lg border border-cyan-500/30 bg-cyan-950/20 px-2 py-2">
              <div className="min-w-0 flex-1">
                <span className="text-[10px] font-semibold uppercase tracking-wide text-cyan-300">
                  Alternate pathway pending
                </span>
                <p className="mt-0.5 line-clamp-2 text-[10px] text-slate-400">
                  {pendingPathway.rationale ||
                    `Approve pivot to ${pendingPathway.pathway?.label || "alternate pathway"}`}
                </p>
              </div>
            </div>
          )}
          {pending && onApprove ? (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <DirectiveSummary directive={pending} hint={directiveHint} liveCouncil={liveCouncil} />
              <div className="flex shrink-0 flex-col gap-1.5 sm:w-72">
                <input
                  type="text"
                  value={directiveNote}
                  onChange={(e) => setDirectiveNote(e.target.value)}
                  placeholder="Optional directive note…"
                  className="h-7 w-full rounded border border-slate-700 bg-slate-900/80 px-2 font-mono text-[10px] text-slate-300 placeholder:text-slate-600 focus:border-amber-500/40 focus:outline-none"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !approving) void handleApprove();
                  }}
                />
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => void handleApprove()}
                    disabled={approving}
                    className="inline-flex h-7 items-center gap-1 rounded bg-amber-600 px-3 text-[10px] font-medium text-white hover:bg-amber-500 disabled:opacity-50"
                  >
                    {approving ? (
                      <Loader2 className="size-3 animate-spin" />
                    ) : (
                      <ThumbsUp className="size-3" />
                    )}
                    Approve directive
                  </button>
                  {onForceReplan && (
                    <button
                      type="button"
                      onClick={() => void onForceReplan()}
                      disabled={replanning || replans >= maxReplans}
                      className="inline-flex h-7 items-center gap-1 rounded border border-cyan-600/40 bg-cyan-950/40 px-3 text-[10px] font-medium text-cyan-300 hover:bg-cyan-950/70 disabled:opacity-50"
                      title={
                        replans >= maxReplans
                          ? "Max replans reached"
                          : "Force council replan"
                      }
                    >
                      {replanning ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        <RefreshCw className="size-3" />
                      )}
                      Force replan
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            onForceReplan && (
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] text-slate-500">
                  No pending approval — force replan to re-run council analysis.
                </span>
                <button
                  type="button"
                  onClick={() => void onForceReplan()}
                  disabled={replanning || replans >= maxReplans}
                  className="inline-flex h-7 items-center gap-1 rounded border border-cyan-600/40 bg-cyan-950/40 px-3 text-[10px] font-medium text-cyan-300 hover:bg-cyan-950/70 disabled:opacity-50"
                >
                  {replanning ? (
                    <Loader2 className="size-3 animate-spin" />
                  ) : (
                    <RefreshCw className="size-3" />
                  )}
                  Force replan
                </button>
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
