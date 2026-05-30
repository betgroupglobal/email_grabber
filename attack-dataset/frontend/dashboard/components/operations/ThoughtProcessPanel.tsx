"use client";

import { useEffect, useMemo, useState } from "react";
import { Brain, Check, ChevronDown, ChevronRight, Circle, GitBranch, Loader2 } from "lucide-react";
import type { CouncilWsEvent, LiveCouncilState, ReasoningTraceEntry } from "@/lib/liveCouncil";
import {
  STAGE_LABELS,
  THOUGHT_PATTERN_STEPS,
  THOUGHT_PROCESS_CYCLE,
  getStageById,
  mergeThoughtStream,
  resolveCurrentPatternStep,
  resolveSubtaskProgress,
  type SubtaskProgress,
  type ThoughtPatternStep,
  type ThoughtStreamItem,
} from "@/lib/thoughtProcessPattern";
import { cn } from "@/lib/utils";

export interface ThoughtProcessPanelProps {
  reasoningTrace?: ReasoningTraceEntry[];
  councilEvents?: CouncilWsEvent[];
  liveCouncil?: LiveCouncilState;
  currentPhase?: number;
  target?: string;
  className?: string;
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  /** Manual stage transition via templater (Shift+1…7 or stage click). */
  onRunStageTemplate?: (stageId: ThoughtPatternStep) => void | Promise<void>;
}

function StageIndicator({ current }: { current: ThoughtPatternStep }) {
  const currentIdx = THOUGHT_PATTERN_STEPS.indexOf(current);
  return (
    <div className="flex flex-wrap gap-0.5" role="list" aria-label="Thought process stages">
      {THOUGHT_PATTERN_STEPS.map((step, i) => {
        const active = step === current;
        const done = i < currentIdx;
        return (
          <div
            key={step}
            role="listitem"
            className={cn(
              "rounded px-1 py-0.5 font-mono text-[9px] uppercase tracking-wide transition-colors",
              active
                ? "bg-violet-600/40 text-violet-100 ring-1 ring-violet-400/50"
                : done
                  ? "bg-slate-800/80 text-slate-500"
                  : "bg-slate-900/60 text-slate-600"
            )}
            title={STAGE_LABELS[step]}
          >
            {STAGE_LABELS[step].slice(0, 3)}
          </div>
        );
      })}
    </div>
  );
}

function SubtaskStatusIcon({ status }: { status: SubtaskProgress["status"] }) {
  if (status === "complete") {
    return <Check className="size-2.5 shrink-0 text-emerald-400/90" aria-hidden />;
  }
  if (status === "in_progress") {
    return <Loader2 className="size-2.5 shrink-0 animate-spin text-violet-400/90" aria-hidden />;
  }
  return <Circle className="size-2 shrink-0 text-slate-600" aria-hidden />;
}

function SubtaskChecklist({ items }: { items: SubtaskProgress[] }) {
  return (
    <ul className="space-y-0.5" aria-label="Key activities">
      {items.map((item) => (
        <li
          key={item.id}
          className={cn(
            "flex items-start gap-1 font-mono text-[9px] leading-snug",
            item.status === "complete"
              ? "text-slate-500 line-through decoration-slate-600"
              : item.status === "in_progress"
                ? "text-violet-200/90"
                : "text-slate-500"
          )}
          title={item.id}
        >
          <SubtaskStatusIcon status={item.status} />
          <span className="min-w-0 flex-1">{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

function ActiveStageDetail({
  step,
  subtasks,
}: {
  step: ThoughtPatternStep;
  subtasks: SubtaskProgress[];
}) {
  const stage = getStageById(step);
  if (!stage) return null;
  return (
    <div className="rounded border border-violet-500/20 bg-violet-950/10 p-1.5">
      <p className="font-mono text-[9px] font-medium uppercase tracking-wide text-violet-300/90">
        {stage.stage}
      </p>
      <p className="mt-0.5 font-mono text-[9px] leading-snug text-slate-400">{stage.objective}</p>
      <p className="mb-0.5 mt-1.5 font-mono text-[8px] uppercase tracking-wide text-slate-600">
        Key activities
      </p>
      <SubtaskChecklist items={subtasks} />
    </div>
  );
}

function CycleReference({
  currentStep,
  onRunStageTemplate,
}: {
  currentStep: ThoughtPatternStep;
  onRunStageTemplate?: (stageId: ThoughtPatternStep) => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="shrink-0 border-t border-slate-800/80 pt-1.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1 font-mono text-[9px] uppercase tracking-wide text-slate-600 hover:text-slate-400"
        aria-expanded={open}
      >
        {open ? <ChevronDown className="size-2.5" /> : <ChevronRight className="size-2.5" />}
        Full cycle
      </button>
      {open && (
        <div className="mt-1 max-h-32 space-y-1 overflow-y-auto">
          {THOUGHT_PROCESS_CYCLE.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => void onRunStageTemplate?.(s.id)}
              disabled={!onRunStageTemplate || s.id === currentStep}
              className={cn(
                "w-full rounded px-1 py-0.5 text-left transition-colors",
                s.id === currentStep ? "bg-slate-800/60" : "opacity-70 hover:bg-slate-800/40",
                onRunStageTemplate && s.id !== currentStep && "cursor-pointer",
                !onRunStageTemplate && "cursor-default"
              )}
              title={onRunStageTemplate ? `Run template: jump to ${s.stage}` : s.stage}
            >
              <p className="font-mono text-[9px] font-medium text-slate-400">{s.stage}</p>
              <p className="line-clamp-1 font-mono text-[8px] text-slate-600">{s.objective}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ThoughtRow({ item }: { item: ThoughtStreamItem }) {
  return (
    <div className="rounded border border-slate-800/80 bg-slate-950/60 px-2 py-1.5">
      <div className="flex flex-wrap items-center gap-1">
        <span className="font-mono text-[9px] font-semibold uppercase text-violet-300/90">
          {item.stage}
        </span>
        {item.subtaskId && (
          <span className="font-mono text-[8px] text-slate-600">{item.subtaskId}</span>
        )}
        {item.source && (
          <span className="font-mono text-[9px] text-slate-600">{item.source}</span>
        )}
        {item.turn != null && (
          <span className="font-mono text-[9px] text-slate-600">t{item.turn}</span>
        )}
      </div>
      <p className="mt-0.5 line-clamp-3 font-mono text-[10px] leading-snug text-slate-400">
        <span className="text-slate-500">[think]</span> {item.text}
      </p>
      {item.alternatePathways && item.alternatePathways.length > 0 && (
        <div className="mt-1 flex flex-wrap items-center gap-1 text-[9px] text-cyan-400/90">
          <GitBranch className="size-2.5 shrink-0" />
          {item.alternatePathways.slice(0, 3).join(" · ")}
        </div>
      )}
    </div>
  );
}

export function ThoughtProcessPanel({
  reasoningTrace,
  councilEvents,
  liveCouncil,
  currentPhase,
  target,
  className,
  collapsed: collapsedProp,
  onCollapsedChange,
  onRunStageTemplate,
}: ThoughtProcessPanelProps) {
  const [collapsedInternal, setCollapsedInternal] = useState(collapsedProp ?? false);
  const collapsed = collapsedProp ?? collapsedInternal;
  const setCollapsed = (v: boolean) => {
    setCollapsedInternal(v);
    onCollapsedChange?.(v);
  };

  useEffect(() => {
    if (collapsedProp !== undefined) setCollapsedInternal(collapsedProp);
  }, [collapsedProp]);

  const currentStep = useMemo(
    () =>
      resolveCurrentPatternStep({
        reasoningTrace,
        liveCouncil,
        currentPhase,
        targetSet: Boolean(target?.trim()),
      }),
    [reasoningTrace, liveCouncil, currentPhase, target]
  );

  const activeSubtasks = useMemo(
    () =>
      resolveSubtaskProgress({
        stageId: currentStep,
        reasoningTrace,
        currentPhase,
        targetSet: Boolean(target?.trim()),
        liveCouncil,
      }),
    [currentStep, reasoningTrace, currentPhase, target, liveCouncil]
  );

  const thoughts = useMemo(
    () => mergeThoughtStream(reasoningTrace, councilEvents).slice(-12),
    [reasoningTrace, councilEvents]
  );

  const conductorRationale = liveCouncil?.pending_directive?.rationale;
  const pendingPathway = liveCouncil?.pending_pathway;

  return (
    <aside
      className={cn(
        "flex shrink-0 flex-col border-r border-slate-800 bg-[#0a0e14]/95",
        collapsed ? "w-10" : "w-52 sm:w-60",
        className
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="flex shrink-0 items-center gap-1.5 border-b border-slate-800 px-2 py-1.5 text-left hover:bg-slate-900/50"
        aria-expanded={!collapsed}
      >
        <Brain className="size-3 shrink-0 text-violet-400" />
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1 font-mono text-[10px] font-medium uppercase tracking-wide text-slate-400">
              Thought rail
            </span>
            <ChevronDown className="size-3 text-slate-600" />
          </>
        )}
        {collapsed && <ChevronRight className="size-3 text-slate-600" />}
      </button>

      {!collapsed && (
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-2">
          <div>
            <p className="mb-1 font-mono text-[9px] uppercase tracking-wide text-slate-600">
              Current · {STAGE_LABELS[currentStep]}
            </p>
            <StageIndicator current={currentStep} />
          </div>

          <ActiveStageDetail step={currentStep} subtasks={activeSubtasks} />

          {target && (
            <p className="line-clamp-2 font-mono text-[9px] text-slate-500" title={target}>
              Target: {target}
            </p>
          )}

          {(conductorRationale || pendingPathway) && (
            <div className="shrink-0 space-y-1 rounded border border-amber-500/25 bg-amber-950/15 p-1.5">
              {conductorRationale && (
                <p className="font-mono text-[9px] leading-snug text-amber-200/90">
                  <span className="text-amber-400/80">Conductor:</span>{" "}
                  {conductorRationale.slice(0, 160)}
                  {conductorRationale.length > 160 ? "…" : ""}
                </p>
              )}
              {pendingPathway && (
                <p className="font-mono text-[9px] leading-snug text-cyan-300/90">
                  <span className="text-cyan-400/80">Pathway:</span>{" "}
                  {pendingPathway.rationale ||
                    pendingPathway.pathway?.label ||
                    "Alternate route pending approval"}
                </p>
              )}
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto">
            <p className="mb-1 font-mono text-[9px] uppercase tracking-wide text-slate-600">
              Stream
            </p>
            {thoughts.length === 0 ? (
              <p className="font-mono text-[10px] text-slate-600">
                Reasoning appears when the run faces the target…
              </p>
            ) : (
              <div className="space-y-1.5">
                {thoughts.map((item) => (
                  <ThoughtRow key={item.id} item={item} />
                ))}
              </div>
            )}
          </div>

          <CycleReference currentStep={currentStep} onRunStageTemplate={onRunStageTemplate} />
        </div>
      )}
    </aside>
  );
}
